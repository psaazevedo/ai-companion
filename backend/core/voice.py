from __future__ import annotations

import base64
import io
import logging
import re
import wave
from typing import Optional

import httpx
from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)


class VoiceProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = (
            AsyncOpenAI(
                api_key=self.settings.groq_api_key,
                base_url=self.settings.groq_base_url,
            )
            if self.settings.groq_api_key
            else None
        )

    async def transcribe(self, audio_data: bytes, audio_filename: str = "audio.webm") -> str:
        if not self.settings.transcription_enabled or self.client is None:
            return "I received voice audio, but Groq transcription is still running in mock mode."

        audio_file = io.BytesIO(audio_data)
        audio_file.name = audio_filename

        result = await self.client.audio.transcriptions.create(
            model=self.settings.groq_transcription_model,
            file=audio_file,
            response_format="json",
        )
        return result.text.strip()

    async def speak(self, text: str) -> Optional[str]:
        if not self.settings.tts_enabled:
            return None

        url = f"{self.settings.groq_base_url}/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "accept": self.output_mime_type,
            "content-type": "application/json",
        }

        chunks = self._chunk_text(self._prepare_tts_text(text))
        if not chunks:
            return None

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                audio_parts: list[bytes] = []
                for chunk in chunks:
                    payload = {
                        "model": self.settings.groq_tts_model,
                        "voice": self.settings.groq_tts_voice,
                        "input": chunk,
                        "response_format": self.settings.groq_tts_response_format,
                    }
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    audio_parts.append(response.content)

                audio_bytes = self._merge_wav_chunks(audio_parts)
                return base64.b64encode(audio_bytes).decode("utf-8")
            except httpx.HTTPStatusError as exc:
                body = exc.response.text.strip()
                logger.warning("Groq TTS request failed: %s", body or str(exc))
                return None
            except Exception:
                logger.exception("Unexpected Groq TTS failure")
                return None

    def _prepare_tts_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        style = self.settings.groq_tts_style.strip()
        if style:
            return f"[{style}] {cleaned}"
        return cleaned

    def _chunk_text(self, text: str, limit: int = 200) -> list[str]:
        if not text:
            return []

        parts = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        current = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if len(part) > limit:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(self._split_long_segment(part, limit))
                continue

            candidate = part if not current else f"{current} {part}"
            if len(candidate) <= limit:
                current = candidate
            else:
                chunks.append(current)
                current = part

        if current:
            chunks.append(current)

        return chunks

    def _split_long_segment(self, text: str, limit: int) -> list[str]:
        words = text.split()
        chunks: list[str] = []
        current = ""

        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = word[:limit]

        if current:
            chunks.append(current)

        return chunks

    def _merge_wav_chunks(self, chunks: list[bytes]) -> bytes:
        if not chunks:
            return b""
        if len(chunks) == 1:
            return chunks[0]

        output = io.BytesIO()
        with wave.open(io.BytesIO(chunks[0]), "rb") as first:
            params = first.getparams()
            frames = [first.readframes(first.getnframes())]

        for chunk in chunks[1:]:
            with wave.open(io.BytesIO(chunk), "rb") as wav_file:
                if wav_file.getparams()[:3] != params[:3]:
                    raise ValueError("Incompatible WAV chunk parameters from Groq TTS")
                frames.append(wav_file.readframes(wav_file.getnframes()))

        with wave.open(output, "wb") as merged:
            merged.setparams(params)
            for frame_bytes in frames:
                merged.writeframes(frame_bytes)

        return output.getvalue()

    @property
    def output_mime_type(self) -> str:
        return {
            "flac": "audio/flac",
            "mp3": "audio/mpeg",
            "mulaw": "audio/basic",
            "ogg": "audio/ogg",
            "wav": "audio/wav",
        }.get(self.settings.groq_tts_response_format.lower(), "audio/mpeg")
