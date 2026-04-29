import asyncio
import base64
import logging
import re
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from core.agent import format_for_voice_delivery, get_agent

logger = logging.getLogger(__name__)

MINIMUM_SPEECH_ACTIVE_MS = 180.0
MINIMUM_SPEECH_PEAK_LEVEL = 0.08


def register_websocket_routes(app: FastAPI) -> None:
    @app.websocket("/ws/{user_id}")
    async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        agent = get_agent()
        send_lock = asyncio.Lock()
        current_turn_task: Optional[asyncio.Task[Any]] = None
        current_turn_id: Optional[int] = None
        pending_audio_turn_id: Optional[int] = None
        pending_audio_chunks: list[bytes] = []
        pending_audio_filename = "audio.webm"
        pending_audio_stream_response = False
        pending_audio_metadata: dict[str, Any] = {}
        turn_counter = 0

        async def send_event(payload: dict[str, Any]) -> None:
            async with send_lock:
                await websocket.send_json(payload)

        def consume_task_result(task: asyncio.Task[Any]) -> None:
            try:
                task.result()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Detached turn task failed")

        async def cancel_current_turn(reason: str, announce: bool) -> bool:
            nonlocal current_turn_id, current_turn_task, pending_audio_turn_id, pending_audio_chunks, pending_audio_filename, pending_audio_stream_response, pending_audio_metadata

            task = current_turn_task
            had_active_turn = bool(task and not task.done())
            had_pending_audio = pending_audio_turn_id is not None or bool(pending_audio_chunks)
            current_turn_id = None
            current_turn_task = None
            pending_audio_turn_id = None
            pending_audio_chunks = []
            pending_audio_filename = "audio.webm"
            pending_audio_stream_response = False
            pending_audio_metadata = {}

            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=1.5)
                except asyncio.TimeoutError:
                    logger.warning("Timed out waiting for turn cancellation for user %s", user_id)
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("Turn cancellation cleanup failed")

            if announce and (had_active_turn or had_pending_audio):
                await send_event(
                    {
                        "type": "interrupted",
                        "reason": reason,
                    }
                )

            return had_active_turn or had_pending_audio

        async def handle_turn(
            turn_id: int,
            message_type: str,
            data: dict[str, Any],
            audio_data: Optional[bytes] = None,
            audio_filename: Optional[str] = None,
            prefer_streaming_response: bool = False,
        ) -> None:
            nonlocal current_turn_id, current_turn_task

            try:
                await send_event({"type": "thinking", "turnId": turn_id})

                if prefer_streaming_response:
                    await send_event({"type": "response_start", "turnId": turn_id})
                    sentence_buffer = ""
                    streamed_audio_segments = 0

                    stream = (
                        agent.stream_input(
                            user_id=user_id,
                            audio_data=audio_data or base64.b64decode(str(data.get("audio"))),
                            audio_filename=audio_filename,
                            conversation_mode=_conversation_mode(data),
                            visibility_scope=_visibility_scope(data),
                            allowed_modes=_allowed_modes(data),
                        )
                        if message_type == "audio"
                        else agent.stream_input(
                            user_id=user_id,
                            user_input=str(data.get("text", "")).strip(),
                            conversation_mode=_conversation_mode(data),
                            visibility_scope=_visibility_scope(data),
                            allowed_modes=_allowed_modes(data),
                        )
                    )

                    async for event in stream:
                        if current_turn_id != turn_id:
                            return

                        if event["type"] == "delta":
                            chunk = str(event["text"])
                            sentence_buffer += chunk
                            await send_event(
                                {
                                    "type": "response_delta",
                                    "turnId": turn_id,
                                    "text": chunk,
                                }
                            )
                            completed, sentence_buffer = _drain_completed_sentences(sentence_buffer)
                            for sentence in completed:
                                spoken_sentence = format_for_voice_delivery(sentence)
                                if not spoken_sentence:
                                    continue
                                sentence_audio = await agent.voice.speak(spoken_sentence)
                                if sentence_audio:
                                    streamed_audio_segments += 1
                                await send_event(
                                    {
                                        "type": "response_sentence",
                                        "turnId": turn_id,
                                        "text": spoken_sentence,
                                        "audio": sentence_audio,
                                        "audioMimeType": (
                                            agent.voice.output_mime_type if sentence_audio else None
                                        ),
                                    }
                                )
                            continue

                        if sentence_buffer.strip():
                            spoken_sentence = format_for_voice_delivery(sentence_buffer.strip())
                            if spoken_sentence:
                                sentence_audio = await agent.voice.speak(spoken_sentence)
                                if sentence_audio:
                                    streamed_audio_segments += 1
                                await send_event(
                                    {
                                        "type": "response_sentence",
                                        "turnId": turn_id,
                                        "text": spoken_sentence,
                                        "audio": sentence_audio,
                                        "audioMimeType": (
                                            agent.voice.output_mime_type if sentence_audio else None
                                        ),
                                    }
                                )
                            sentence_buffer = ""

                        final_text = format_for_voice_delivery(str(event["text"]))
                        final_audio = None
                        if streamed_audio_segments == 0:
                            final_audio = await agent.voice.speak(final_text)
                        await send_event(
                            {
                                "type": "response_complete",
                                "turnId": turn_id,
                                "text": final_text,
                                "audio": final_audio,
                                "audioMimeType": (
                                    agent.voice.output_mime_type if final_audio else None
                                ),
                                "confidence": event["confidence"],
                                "transcript": event["transcript"],
                                "pauseToleranceSeconds": event["pause_tolerance_seconds"],
                            }
                        )
                else:
                    if message_type == "audio":
                        response = await agent.process_input(
                            user_id=user_id,
                            audio_data=audio_data or base64.b64decode(str(data.get("audio"))),
                            audio_filename=audio_filename,
                            conversation_mode=_conversation_mode(data),
                            visibility_scope=_visibility_scope(data),
                            allowed_modes=_allowed_modes(data),
                        )
                    else:
                        response = await agent.process_input(
                            user_id=user_id,
                            user_input=str(data.get("text", "")).strip(),
                            conversation_mode=_conversation_mode(data),
                            visibility_scope=_visibility_scope(data),
                            allowed_modes=_allowed_modes(data),
                        )

                    if current_turn_id != turn_id:
                        return

                    await send_event(
                        {
                            "type": "response",
                            "turnId": turn_id,
                            "text": response.text,
                            "audio": response.audio_base64,
                            "audioMimeType": response.audio_mime_type,
                            "confidence": response.confidence,
                            "transcript": response.transcript,
                            "pauseToleranceSeconds": response.pause_tolerance_seconds,
                        }
                    )
            except asyncio.CancelledError:
                logger.info("Cancelled turn %s for user %s", turn_id, user_id)
                raise
            except Exception as exc:  # pragma: no cover - keep socket alive on request failures
                logger.exception("WebSocket request failed")
                if current_turn_id == turn_id:
                    await send_event(
                        {
                            "type": "error",
                            "turnId": turn_id,
                            "message": str(exc),
                        }
                    )
            finally:
                if current_turn_task is asyncio.current_task():
                    current_turn_task = None
                    current_turn_id = None

        await send_event(
            {
                "type": "ready",
                "userId": user_id,
                "pauseToleranceSeconds": float(
                    (await agent.memory.dialogue_profile(user_id)).get("pause_tolerance_seconds", 0.9)
                ),
            }
        )

        try:
            while True:
                try:
                    data: dict[str, Any] = await websocket.receive_json()
                    message_type = str(data.get("type", "")).strip()

                    if message_type == "interrupt":
                        interrupted = await cancel_current_turn(reason="user", announce=True)
                        if not interrupted:
                            await send_event(
                                {
                                    "type": "interrupted",
                                    "reason": "idle",
                                }
                            )
                        continue

                    if message_type == "input_start":
                        turn_id = _coerce_turn_id(data.get("turnId"))
                        if turn_id is None:
                            await send_event(
                                {
                                    "type": "error",
                                    "message": "Missing turn ID for input_start.",
                                }
                            )
                            continue

                        if current_turn_task and not current_turn_task.done():
                            await cancel_current_turn(reason="superseded", announce=False)

                        pending_audio_turn_id = turn_id
                        pending_audio_chunks = []
                        pending_audio_filename = _audio_filename_for_mime(
                            str(data.get("audioMimeType") or data.get("mimeType") or "")
                        )
                        pending_audio_stream_response = bool(data.get("preferStreamingResponse"))
                        pending_audio_metadata = {
                            "conversationMode": data.get("conversationMode") or data.get("conversation_mode"),
                            "visibilityScope": data.get("visibilityScope") or data.get("visibility_scope"),
                            "allowedModes": data.get("allowedModes") or data.get("allowed_modes"),
                        }
                        turn_counter = max(turn_counter, turn_id)
                        await send_event(
                            {
                                "type": "listening",
                                "turnId": turn_id,
                            }
                        )
                        continue

                    if message_type == "input_cancel":
                        turn_id = _coerce_turn_id(data.get("turnId"))
                        if turn_id is not None and turn_id == pending_audio_turn_id:
                            pending_audio_turn_id = None
                            pending_audio_chunks = []
                            pending_audio_filename = "audio.webm"
                            pending_audio_stream_response = False
                            pending_audio_metadata = {}
                        await send_event(
                            {
                                "type": "ready",
                                "turnId": turn_id,
                                "pauseToleranceSeconds": float(
                                    (await agent.memory.dialogue_profile(user_id)).get(
                                        "pause_tolerance_seconds",
                                        0.9,
                                    )
                                ),
                            }
                        )
                        continue

                    if message_type == "audio_chunk":
                        turn_id = _coerce_turn_id(data.get("turnId"))
                        if turn_id is None or turn_id != pending_audio_turn_id:
                            await send_event(
                                {
                                    "type": "error",
                                    "message": "Received audio chunk for an unknown turn.",
                                }
                            )
                            continue

                        audio_payload = data.get("audio")
                        if not audio_payload:
                            await send_event(
                                {
                                    "type": "error",
                                    "message": "Missing audio chunk payload.",
                                }
                            )
                            continue

                        pending_audio_chunks.append(base64.b64decode(str(audio_payload)))
                        continue

                    if message_type == "input_end":
                        turn_id = _coerce_turn_id(data.get("turnId"))
                        if turn_id is None or turn_id != pending_audio_turn_id:
                            await send_event(
                                {
                                    "type": "error",
                                    "message": "Received input_end for an unknown turn.",
                                }
                            )
                            continue

                        speech_active_ms = _coerce_float(data.get("speechActiveMs"))
                        peak_input_level = _coerce_float(data.get("peakInputLevel"))
                        if (
                            speech_active_ms is not None
                            and peak_input_level is not None
                            and (
                                speech_active_ms < MINIMUM_SPEECH_ACTIVE_MS
                                or peak_input_level < MINIMUM_SPEECH_PEAK_LEVEL
                            )
                        ):
                            pending_audio_turn_id = None
                            pending_audio_chunks = []
                            pending_audio_filename = "audio.webm"
                            pending_audio_stream_response = False
                            await send_event(
                                {
                                    "type": "ready",
                                    "turnId": turn_id,
                                    "pauseToleranceSeconds": float(
                                        (await agent.memory.dialogue_profile(user_id)).get(
                                            "pause_tolerance_seconds",
                                            0.9,
                                        )
                                    ),
                                }
                            )
                            continue

                        if not pending_audio_chunks:
                            pending_audio_turn_id = None
                            pending_audio_filename = "audio.webm"
                            await send_event(
                                {
                                    "type": "error",
                                    "message": "No audio chunks were received for this turn.",
                                }
                            )
                            continue

                        if current_turn_task and not current_turn_task.done():
                            await cancel_current_turn(reason="superseded", announce=False)

                        audio_bytes = b"".join(pending_audio_chunks)
                        audio_filename = pending_audio_filename
                        prefer_streaming_response = pending_audio_stream_response
                        metadata = pending_audio_metadata
                        pending_audio_turn_id = None
                        pending_audio_chunks = []
                        pending_audio_filename = "audio.webm"
                        pending_audio_stream_response = False
                        pending_audio_metadata = {}
                        turn_counter = max(turn_counter, turn_id)
                        current_turn_id = turn_id
                        current_turn_task = asyncio.create_task(
                            handle_turn(
                                turn_id,
                                "audio",
                                metadata,
                                audio_data=audio_bytes,
                                audio_filename=audio_filename,
                                prefer_streaming_response=prefer_streaming_response,
                            )
                        )
                        current_turn_task.add_done_callback(consume_task_result)
                        continue

                    if message_type not in {"audio", "text"}:
                        await send_event(
                            {
                                "type": "error",
                                "message": "Unsupported message type.",
                            }
                        )
                        continue

                    if message_type == "audio" and not data.get("audio"):
                        await send_event(
                            {
                                "type": "error",
                                "message": "Missing audio payload.",
                            }
                        )
                        continue

                    if current_turn_task and not current_turn_task.done():
                        await cancel_current_turn(reason="superseded", announce=False)

                    turn_counter += 1
                    current_turn_id = turn_counter
                    prefer_streaming_response = bool(data.get("preferStreamingResponse"))
                    current_turn_task = asyncio.create_task(
                        handle_turn(
                            current_turn_id,
                            message_type,
                            data,
                            prefer_streaming_response=prefer_streaming_response,
                        )
                    )
                    current_turn_task.add_done_callback(consume_task_result)
                except WebSocketDisconnect:
                    raise
                except Exception as exc:  # pragma: no cover - keep socket alive on request failures
                    logger.exception("WebSocket receive loop failed")
                    await send_event(
                        {
                            "type": "error",
                            "message": str(exc),
                        }
                    )
        except WebSocketDisconnect:
            if current_turn_task and not current_turn_task.done():
                current_turn_task.cancel()
            return


def _coerce_turn_id(raw_value: Any) -> Optional[int]:
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _coerce_float(raw_value: Any) -> Optional[float]:
    if raw_value is None:
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _audio_filename_for_mime(mime_type: str) -> str:
    normalized = mime_type.strip().lower()
    if "wav" in normalized:
        return "audio.wav"
    if "mpeg" in normalized or "mp3" in normalized:
        return "audio.mp3"
    if "mp4" in normalized or "m4a" in normalized:
        return "audio.mp4"
    if "ogg" in normalized:
        return "audio.ogg"
    return "audio.webm"


def _conversation_mode(data: dict[str, Any]) -> str:
    raw_value = data.get("conversationMode") or data.get("conversation_mode") or "general"
    normalized = re.sub(r"[^a-z0-9]+", "-", str(raw_value).lower()).strip("-")
    return normalized or "general"


def _visibility_scope(data: dict[str, Any]) -> Optional[str]:
    raw_value = data.get("visibilityScope") or data.get("visibility_scope")
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().lower()
    return normalized if normalized in {"global", "restricted", "private"} else None


def _allowed_modes(data: dict[str, Any]) -> Optional[list[str]]:
    raw_value = data.get("allowedModes") or data.get("allowed_modes")
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        values = [raw_value]
    elif isinstance(raw_value, list):
        values = [str(value) for value in raw_value]
    else:
        return None
    return [re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") for value in values if value]


def _drain_completed_sentences(buffer: str) -> tuple[list[str], str]:
    sentences: list[str] = []
    remainder = buffer
    pattern = re.compile(r"^\s*(.+?[.!?](?:['\"”])?)(?=\s+|$)", re.S)

    while True:
        match = pattern.match(remainder)
        if not match:
            break
        sentence = match.group(1).strip()
        if sentence:
            sentences.append(sentence)
        remainder = remainder[match.end() :]

    return sentences, remainder
