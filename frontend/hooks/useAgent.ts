import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { Audio, InterruptionModeIOS } from "expo-av";
import * as FileSystem from "expo-file-system";
import * as Speech from "expo-speech";
import { Platform } from "react-native";

import { getWebSocketBaseUrl } from "@/services/api";
import { useAgentStore, type ConversationState } from "@/stores/agentStore";

type ServerPayload = {
  type: string;
  text?: string;
  audio?: string | null;
  audioMimeType?: string | null;
  message?: string;
  reason?: string;
  pauseToleranceSeconds?: number;
  turnId?: number;
};

const MINIMUM_SPEECH_ACTIVE_MS = 180;
const MINIMUM_SPEECH_PEAK_LEVEL = 0.08;

export function useAgent() {
  const [responsePreview, setResponsePreview] = useState("");
  const responsePreviewRef = useRef("");
  const soundRef = useRef<Audio.Sound | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef(true);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const playbackTokenRef = useRef(0);
  const chunkSendQueueRef = useRef<Promise<void>>(Promise.resolve());
  const streamAudioQueueRef = useRef<Promise<void>>(Promise.resolve());
  const activeInputTurnIdRef = useRef<number | null>(null);
  const nextTurnIdRef = useRef(0);
  const activeStreamPlaybackTokenRef = useRef<number | null>(null);
  const pendingSpeechSegmentsRef = useRef(0);
  const streamedSentenceCountRef = useRef(0);
  const streamCompleteRef = useRef(false);
  const pauseToleranceSecondsRef = useRef(0.9);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserNodeRef = useRef<AnalyserNode | null>(null);
  const analyserDataRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const mediaSourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const silenceCheckFrameRef = useRef<number | null>(null);
  const speechDetectedRef = useRef(false);
  const speechActiveMsRef = useRef(0);
  const peakInputLevelRef = useRef(0);
  const lastMonitorAtRef = useRef(0);
  const lastSpeechAtRef = useRef(0);
  const listeningStartedAtRef = useRef(0);
  const autoStopInFlightRef = useRef(false);

  const {
    isConnected,
    isListening,
    isSpeaking,
    isThinking,
    statusMessage,
    setConnected,
    setConversationState,
    setListening,
    setSpeaking,
    setThinking,
    setOrbInputLevel,
    setStatusMessage,
    bumpMemoryRefreshKey,
  } = useAgentStore();

  useEffect(() => {
    const wsBase = getWebSocketBaseUrl();
    const userId = "local-user";

    const scheduleReconnect = () => {
      if (!shouldReconnectRef.current || reconnectTimeoutRef.current) {
        return;
      }

      reconnectTimeoutRef.current = setTimeout(() => {
        reconnectTimeoutRef.current = null;
        connect();
      }, 1200);
    };

    const connect = () => {
      const socket = new WebSocket(`${wsBase}/${userId}`);
      socketRef.current = socket;

      socket.onopen = () => {
        setConnected(true);
        setConversationState("ready");
        setStatusMessage("Ready");
      };

      socket.onclose = () => {
        socketRef.current = null;
        activeInputTurnIdRef.current = null;
        responsePreviewRef.current = "";
        setResponsePreview("");
        chunkSendQueueRef.current = Promise.resolve();
        streamAudioQueueRef.current = Promise.resolve();
        streamedSentenceCountRef.current = 0;
        setOrbInputLevel(0);
        stopAudioMonitoring({
          analyserNodeRef,
          audioContextRef,
          mediaSourceNodeRef,
          silenceCheckFrameRef,
        });
        void stopSpeakingOutput(soundRef, playbackTokenRef);
        setConnected(false);
        setConversationState(shouldReconnectRef.current ? "reconnecting" : "error");
        setListening(false);
        setThinking(false);
        setSpeaking(false);

        if (!shouldReconnectRef.current) {
          return;
        }

        setStatusMessage("Reconnecting...");
        scheduleReconnect();
      };

      socket.onerror = () => {
        setConnected(false);
        setConversationState(shouldReconnectRef.current ? "reconnecting" : "error");
        if (shouldReconnectRef.current) {
          setStatusMessage("Reconnecting...");
        } else {
          setStatusMessage("WebSocket error. Check that the backend is running.");
        }
      };

      socket.onmessage = async (event) => {
        const payload = JSON.parse(event.data) as ServerPayload;

        if (payload.type === "ready") {
          if (typeof payload.pauseToleranceSeconds === "number") {
            pauseToleranceSecondsRef.current = payload.pauseToleranceSeconds;
          }
          setConversationState("ready");
          setStatusMessage("Ready");
          return;
        }

        if (payload.type === "listening") {
          if (activeInputTurnIdRef.current === payload.turnId) {
            setConversationState("listening");
            setListening(true);
            setStatusMessage("Listening...");
          }
          return;
        }

        if (payload.type === "thinking") {
          setOrbInputLevel(0);
          setConversationState("thinking");
          setListening(false);
          setThinking(true);
          setSpeaking(false);
          setStatusMessage("Thinking...");
          return;
        }

        if (payload.type === "interrupted") {
          await stopSpeakingOutput(soundRef, playbackTokenRef);
          stopAudioMonitoring({
            analyserNodeRef,
            audioContextRef,
            mediaSourceNodeRef,
            silenceCheckFrameRef,
          });
          responsePreviewRef.current = "";
          setResponsePreview("");
          pendingSpeechSegmentsRef.current = 0;
          streamedSentenceCountRef.current = 0;
          streamCompleteRef.current = false;
          activeStreamPlaybackTokenRef.current = null;
          streamAudioQueueRef.current = Promise.resolve();
          setOrbInputLevel(0);
          setThinking(false);
          setSpeaking(false);

          if (useAgentStore.getState().isListening) {
            setConversationState("listening");
            setStatusMessage("Listening...");
          } else {
            setConversationState("ready");
            setStatusMessage("Ready");
          }
          return;
        }

        if (payload.type === "error") {
          if (activeInputTurnIdRef.current === payload.turnId) {
            activeInputTurnIdRef.current = null;
            setListening(false);
          }
          stopAudioMonitoring({
            analyserNodeRef,
            audioContextRef,
            mediaSourceNodeRef,
            silenceCheckFrameRef,
          });
          responsePreviewRef.current = "";
          setResponsePreview("");
          setConversationState("error");
          setThinking(false);
          setSpeaking(false);
          streamAudioQueueRef.current = Promise.resolve();
          streamedSentenceCountRef.current = 0;
          setOrbInputLevel(0);
          setStatusMessage(payload.message ?? "Something went wrong.");
          return;
        }

        if (payload.type === "response_start") {
          const playbackToken = await resetSpeechChannel(soundRef, playbackTokenRef);
          activeStreamPlaybackTokenRef.current = playbackToken;
          pendingSpeechSegmentsRef.current = 0;
          streamedSentenceCountRef.current = 0;
          streamCompleteRef.current = false;
          streamAudioQueueRef.current = Promise.resolve();
          setOrbInputLevel(0);
          responsePreviewRef.current = "";
          setResponsePreview("");
          setConversationState("speaking");
          setThinking(false);
          setSpeaking(true);
          setStatusMessage("Replying...");
          return;
        }

        if (payload.type === "response_delta") {
          const nextPreview = `${responsePreviewRef.current}${payload.text ?? ""}`;
          responsePreviewRef.current = nextPreview;
          setResponsePreview(nextPreview);
          return;
        }

        if (payload.type === "response_sentence") {
          const sentence = (payload.text ?? "").trim();
          const playbackToken = activeStreamPlaybackTokenRef.current;
          if (!sentence || playbackToken === null || !payload.audio) {
            return;
          }

          pendingSpeechSegmentsRef.current += 1;
          streamedSentenceCountRef.current += 1;
          queueStreamingSpeechSegment({
            onSegmentComplete: () => {
              pendingSpeechSegmentsRef.current = Math.max(
                0,
                pendingSpeechSegmentsRef.current - 1
              );
              maybeFinishStreamPlayback({
                playbackToken,
                playbackTokenRef,
                pendingSpeechSegmentsRef,
                setConversationState,
                setSpeaking,
                setStatusMessage,
                streamCompleteRef,
              });
            },
            playbackToken,
            playbackTokenRef,
            audio: payload.audio,
            audioMimeType: payload.audioMimeType ?? null,
            soundRef,
            sentence,
            streamAudioQueueRef,
          });
          return;
        }

        if (payload.type === "response_complete") {
          activeInputTurnIdRef.current = null;
          streamCompleteRef.current = true;
          if (typeof payload.pauseToleranceSeconds === "number") {
            pauseToleranceSecondsRef.current = payload.pauseToleranceSeconds;
          }
          const finalText = payload.text ?? responsePreviewRef.current;
          if (finalText) {
            responsePreviewRef.current = finalText;
            setResponsePreview(finalText);
          }
          bumpMemoryRefreshKey();

          const playbackToken = activeStreamPlaybackTokenRef.current;
          if (
            playbackToken !== null &&
            pendingSpeechSegmentsRef.current === 0 &&
            streamedSentenceCountRef.current === 0 &&
            finalText.trim()
          ) {
            pendingSpeechSegmentsRef.current = 1;
            queueStreamingSpeechSegment({
              onSegmentComplete: () => {
                pendingSpeechSegmentsRef.current = 0;
                maybeFinishStreamPlayback({
                  playbackToken,
                  playbackTokenRef,
                  pendingSpeechSegmentsRef,
                  setConversationState,
                  setSpeaking,
                  setStatusMessage,
                  streamCompleteRef,
                });
              },
              playbackToken,
              playbackTokenRef,
              audio: payload.audio ?? null,
              audioMimeType: payload.audioMimeType ?? null,
              soundRef,
              sentence: finalText.trim(),
              streamAudioQueueRef,
            });
            return;
          }

          maybeFinishStreamPlayback({
            playbackToken,
            playbackTokenRef,
            pendingSpeechSegmentsRef,
            setConversationState,
            setSpeaking,
            setStatusMessage,
            streamCompleteRef,
          });
          return;
        }

        if (payload.type !== "response") {
          return;
        }

        if (activeInputTurnIdRef.current === payload.turnId) {
          activeInputTurnIdRef.current = null;
        }
        if (typeof payload.pauseToleranceSeconds === "number") {
          pauseToleranceSecondsRef.current = payload.pauseToleranceSeconds;
        }

        const playbackToken = await resetSpeechChannel(soundRef, playbackTokenRef);
        activeStreamPlaybackTokenRef.current = null;
        pendingSpeechSegmentsRef.current = 0;
        streamCompleteRef.current = false;
        streamedSentenceCountRef.current = 0;
        setOrbInputLevel(0);

        setConversationState("speaking");
        setThinking(false);
        setSpeaking(true);
        setStatusMessage("Speaking...");
        responsePreviewRef.current = payload.text ?? "";
        setResponsePreview(responsePreviewRef.current);
        bumpMemoryRefreshKey();

        const handlePlaybackComplete = () => {
          if (playbackTokenRef.current !== playbackToken) {
            return;
          }
          setConversationState("ready");
          setSpeaking(false);
          if (!useAgentStore.getState().isListening) {
            setStatusMessage("Ready");
          }
        };

          if (payload.audio) {
          try {
            const mimeType = payload.audioMimeType ?? "audio/mpeg";
            const uri = `data:${mimeType};base64,${payload.audio}`;
            const { sound } = await Audio.Sound.createAsync({ uri });
            soundRef.current = sound;
            sound.setOnPlaybackStatusUpdate((status) => {
              if (status.isLoaded && status.didJustFinish) {
                handlePlaybackComplete();
              }
            });
            await sound.playAsync();
            return;
          } catch (error) {
            speakFallback(payload.text ?? "", playbackToken, playbackTokenRef, handlePlaybackComplete);
            return;
          }
        }

        speakFallback(payload.text ?? "", playbackToken, playbackTokenRef, handlePlaybackComplete);
      };
    };

    connect();

    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      socketRef.current?.close();
      responsePreviewRef.current = "";
      setResponsePreview("");
      streamAudioQueueRef.current = Promise.resolve();
      streamedSentenceCountRef.current = 0;
      setOrbInputLevel(0);
      stopAudioMonitoring({
        analyserNodeRef,
        audioContextRef,
        mediaSourceNodeRef,
        silenceCheckFrameRef,
      });
      void stopSpeakingOutput(soundRef, playbackTokenRef);
    };
  }, [
    bumpMemoryRefreshKey,
    setConnected,
    setConversationState,
    setListening,
    setOrbInputLevel,
    setSpeaking,
    setStatusMessage,
    setThinking,
  ]);

  const startListening = async () => {
    if (!isConnected || isListening) {
      return;
    }

    if (isSpeaking || isThinking) {
      await interruptCurrentResponse({
        playbackTokenRef,
        setConversationState,
        setSpeaking,
        setStatusMessage,
        setThinking,
        socketRef,
        soundRef,
      });
    }

    if (Platform.OS === "web") {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mimeType = getSupportedMimeType() ?? "audio/webm";
        const mediaRecorder = MediaRecorder.isTypeSupported(mimeType)
          ? new MediaRecorder(stream, { mimeType })
          : new MediaRecorder(stream);
        const turnId = nextTurnIdRef.current + 1;

        nextTurnIdRef.current = turnId;
        activeInputTurnIdRef.current = turnId;
        chunkSendQueueRef.current = Promise.resolve();
        mediaStreamRef.current = stream;
        mediaRecorderRef.current = mediaRecorder;

        const socket = socketRef.current;
        if (socket?.readyState === WebSocket.OPEN) {
          responsePreviewRef.current = "";
          setResponsePreview("");
          socket.send(
            JSON.stringify({
              type: "input_start",
              turnId,
              audioMimeType: mediaRecorder.mimeType || mimeType,
              preferStreamingResponse: true,
            })
          );
        }

        autoStopInFlightRef.current = false;
        speechDetectedRef.current = false;
        speechActiveMsRef.current = 0;
        peakInputLevelRef.current = 0;
        listeningStartedAtRef.current = performance.now();
        lastSpeechAtRef.current = listeningStartedAtRef.current;
        lastMonitorAtRef.current = listeningStartedAtRef.current;
        startAudioMonitoring({
          activeInputTurnIdRef,
          analyserDataRef,
          analyserNodeRef,
          audioContextRef,
          autoStopInFlightRef,
          listeningStartedAtRef,
          mediaSourceNodeRef,
          onLevel: setOrbInputLevel,
          onEndpoint: () => {
            if (autoStopInFlightRef.current) {
              return;
            }
            autoStopInFlightRef.current = true;
            setStatusMessage("Got it...");
            void stopListening();
          },
          pauseToleranceSecondsRef,
          peakInputLevelRef,
          silenceCheckFrameRef,
          speechActiveMsRef,
          speechDetectedRef,
          lastMonitorAtRef,
          lastSpeechAtRef,
          stream,
          turnId,
        });

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size === 0 || activeInputTurnIdRef.current !== turnId) {
            return;
          }

          chunkSendQueueRef.current = queueAudioChunkSend({
            blob: event.data,
            chunkSendQueueRef,
            socketRef,
            turnId,
          });
        };

        mediaRecorder.start(240);
        setConversationState("listening");
        setListening(true);
        setOrbInputLevel(0);
        setStatusMessage("Listening...");
        return;
      } catch (error) {
        activeInputTurnIdRef.current = null;
        setOrbInputLevel(0);
        setConversationState("error");
        setStatusMessage("Microphone access failed in the browser.");
        return;
      }
    }

    const permission = await Audio.requestPermissionsAsync();
    if (!permission.granted) {
      setOrbInputLevel(0);
      setConversationState("error");
      setStatusMessage("Microphone permission is required.");
      return;
    }

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
      interruptionModeIOS: InterruptionModeIOS.DoNotMix,
      staysActiveInBackground: false,
    });

    const recording = new Audio.Recording();
    await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
    await recording.startAsync();
    recordingRef.current = recording;
    setConversationState("listening");
    setListening(true);
    setOrbInputLevel(0);
    setStatusMessage("Listening...");
  };

  const stopListening = async () => {
    if (Platform.OS === "web") {
      const mediaRecorder = mediaRecorderRef.current;
      const turnId = activeInputTurnIdRef.current;

      if (!mediaRecorder || turnId === null) {
        return;
      }

      setListening(false);
      setOrbInputLevel(0);

      try {
        const hadDetectedSpeech =
          speechDetectedRef.current &&
          speechActiveMsRef.current >= MINIMUM_SPEECH_ACTIVE_MS &&
          peakInputLevelRef.current >= MINIMUM_SPEECH_PEAK_LEVEL;
        stopAudioMonitoring({
          analyserNodeRef,
          audioContextRef,
          mediaSourceNodeRef,
          silenceCheckFrameRef,
        });

        if (!hadDetectedSpeech) {
          await stopStreamedMediaRecorder({
            chunkSendQueueRef,
            mediaRecorder,
            socketRef,
            turnId,
            sendInputEnd: false,
          });

          socketRef.current?.send(
            JSON.stringify({
              type: "input_cancel",
              turnId,
              reason: "no_speech_detected",
            })
          );

          activeInputTurnIdRef.current = null;
          mediaRecorderRef.current = null;
          mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
          mediaStreamRef.current = null;
          autoStopInFlightRef.current = false;
          speechDetectedRef.current = false;
          speechActiveMsRef.current = 0;
          peakInputLevelRef.current = 0;
          lastMonitorAtRef.current = 0;
          setConversationState("ready");
          setThinking(false);
          setStatusMessage("Ready");
          return;
        }

        await stopStreamedMediaRecorder({
          chunkSendQueueRef,
          mediaRecorder,
          peakInputLevel: peakInputLevelRef.current,
          socketRef,
          speechActiveMs: speechActiveMsRef.current,
          turnId,
          sendInputEnd: true,
        });

        mediaRecorderRef.current = null;
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        autoStopInFlightRef.current = false;
        speechDetectedRef.current = false;
        speechActiveMsRef.current = 0;
        peakInputLevelRef.current = 0;
        lastMonitorAtRef.current = 0;

        setConversationState("thinking");
        setThinking(true);
        setStatusMessage("Thinking...");
      } catch (error) {
        activeInputTurnIdRef.current = null;
        mediaRecorderRef.current = null;
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        autoStopInFlightRef.current = false;
        speechDetectedRef.current = false;
        speechActiveMsRef.current = 0;
        peakInputLevelRef.current = 0;
        lastMonitorAtRef.current = 0;
        setConversationState("error");
        setThinking(false);
        setOrbInputLevel(0);
        setStatusMessage("Could not finish recording.");
      }

      return;
    }

    if (!recordingRef.current) {
      return;
    }

    setListening(false);
    setOrbInputLevel(0);

    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      if (!uri) {
        setConversationState("error");
        setOrbInputLevel(0);
        setStatusMessage("Recording failed.");
        return;
      }

      const audioBase64 = await FileSystem.readAsStringAsync(uri, {
        encoding: "base64",
      });

      setConversationState("thinking");
      setThinking(true);
      setStatusMessage("Sending...");

      socketRef.current?.send(
        JSON.stringify({
          type: "audio",
          audio: audioBase64,
        })
      );
    } catch (error) {
      setConversationState("error");
      setThinking(false);
      setOrbInputLevel(0);
      setStatusMessage("Could not finish recording.");
    }
  };

  const sendTextMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !isConnected || isListening) {
      return false;
    }

    if (isSpeaking || isThinking) {
      await interruptCurrentResponse({
        playbackTokenRef,
        setConversationState,
        setSpeaking,
        setStatusMessage,
        setThinking,
        socketRef,
        soundRef,
      });
    }

    responsePreviewRef.current = "";
    setResponsePreview("");
    activeInputTurnIdRef.current = null;
    setOrbInputLevel(0);
    setConversationState("thinking");
    setThinking(true);
    setSpeaking(false);
    setStatusMessage("Sending...");

    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: "text",
          text: trimmed,
          preferStreamingResponse: true,
        })
      );
      return true;
    }

    setConversationState("error");
    setThinking(false);
    setStatusMessage("Connection closed. Restart the app or reconnect the backend.");
    return false;
  };

    return {
      isConnected,
      isListening,
      isSpeaking,
      isThinking,
      responsePreview,
      statusMessage,
      sendTextMessage,
      startListening,
      stopListening,
    };
}

async function resetSpeechChannel(
  soundRef: MutableRefObject<Audio.Sound | null>,
  playbackTokenRef: MutableRefObject<number>
) {
  playbackTokenRef.current += 1;
  const playbackToken = playbackTokenRef.current;
  const activeSound = soundRef.current;
  soundRef.current = null;

  if (activeSound) {
    try {
      await activeSound.stopAsync();
    } catch {}

    try {
      await activeSound.unloadAsync();
    } catch {}
  }

  if (Platform.OS === "web" && typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }

  try {
    await Speech.stop();
  } catch {}

  return playbackToken;
}

async function stopSpeakingOutput(
  soundRef: MutableRefObject<Audio.Sound | null>,
  playbackTokenRef: MutableRefObject<number>
) {
  await resetSpeechChannel(soundRef, playbackTokenRef);
}

function queueStreamingSpeechSegment({
  audio,
  audioMimeType,
  onSegmentComplete,
  playbackToken,
  playbackTokenRef,
  soundRef,
  sentence,
  streamAudioQueueRef,
}: {
  audio: string | null;
  audioMimeType: string | null;
  onSegmentComplete: () => void;
  playbackToken: number;
  playbackTokenRef: MutableRefObject<number>;
  soundRef: MutableRefObject<Audio.Sound | null>;
  sentence: string;
  streamAudioQueueRef: MutableRefObject<Promise<void>>;
}) {
  if (!audio) {
    speakFallback(sentence, playbackToken, playbackTokenRef, onSegmentComplete, false);
    return;
  }

  streamAudioQueueRef.current = streamAudioQueueRef.current
    .catch(() => undefined)
    .then(async () => {
      if (playbackTokenRef.current !== playbackToken) {
        return;
      }

      try {
        await playStreamingAudioSegment({
          audio,
          audioMimeType,
          playbackToken,
          playbackTokenRef,
          soundRef,
        });
      } catch {
        if (playbackTokenRef.current === playbackToken) {
          await new Promise<void>((resolve) => {
            speakFallback(sentence, playbackToken, playbackTokenRef, resolve, false);
          });
        }
      } finally {
        onSegmentComplete();
      }
    });
}

async function playStreamingAudioSegment({
  audio,
  audioMimeType,
  playbackToken,
  playbackTokenRef,
  soundRef,
}: {
  audio: string;
  audioMimeType: string | null;
  playbackToken: number;
  playbackTokenRef: MutableRefObject<number>;
  soundRef: MutableRefObject<Audio.Sound | null>;
}) {
  const mimeType = audioMimeType ?? "audio/wav";
  const uri = `data:${mimeType};base64,${audio}`;
  const { sound } = await Audio.Sound.createAsync({ uri });

  if (playbackTokenRef.current !== playbackToken) {
    try {
      await sound.unloadAsync();
    } catch {}
    return;
  }

  soundRef.current = sound;

  await new Promise<void>((resolve, reject) => {
    let settled = false;

    const finish = (error?: Error) => {
      if (settled) {
        return;
      }
      settled = true;
      sound.setOnPlaybackStatusUpdate(null);
      if (error) {
        reject(error);
        return;
      }
      resolve();
    };

    sound.setOnPlaybackStatusUpdate((status) => {
      if (!status.isLoaded) {
        finish(new Error("Audio segment failed to load."));
        return;
      }

      if (status.didJustFinish) {
        finish();
      }
    });

    sound.playAsync().catch((error) => {
      finish(error instanceof Error ? error : new Error("Audio segment playback failed."));
    });
  });

  if (soundRef.current === sound) {
    soundRef.current = null;
  }

  try {
    await sound.unloadAsync();
  } catch {}
}

function maybeFinishStreamPlayback({
  playbackToken,
  playbackTokenRef,
  pendingSpeechSegmentsRef,
  setConversationState,
  setSpeaking,
  setStatusMessage,
  streamCompleteRef,
}: {
  playbackToken: number | null;
  playbackTokenRef: MutableRefObject<number>;
  pendingSpeechSegmentsRef: MutableRefObject<number>;
  setConversationState: (value: ConversationState) => void;
  setSpeaking: (value: boolean) => void;
  setStatusMessage: (value: string) => void;
  streamCompleteRef: MutableRefObject<boolean>;
}) {
  if (
    playbackToken === null ||
    playbackTokenRef.current !== playbackToken ||
    pendingSpeechSegmentsRef.current > 0 ||
    !streamCompleteRef.current
  ) {
    return;
  }

  setConversationState("ready");
  setSpeaking(false);
  setStatusMessage("Ready");
}

async function interruptCurrentResponse({
  playbackTokenRef,
  setConversationState,
  setSpeaking,
  setStatusMessage,
  setThinking,
  socketRef,
  soundRef,
}: {
  playbackTokenRef: MutableRefObject<number>;
  setConversationState: (value: ConversationState) => void;
  setSpeaking: (value: boolean) => void;
  setStatusMessage: (value: string) => void;
  setThinking: (value: boolean) => void;
  socketRef: MutableRefObject<WebSocket | null>;
  soundRef: MutableRefObject<Audio.Sound | null>;
}) {
  await stopSpeakingOutput(soundRef, playbackTokenRef);
  setConversationState("interrupting");
  setThinking(false);
  setSpeaking(false);
  setStatusMessage("Interrupting...");

  const socket = socketRef.current;
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "interrupt" }));
  }
}

function getSupportedMimeType() {
  if (typeof MediaRecorder === "undefined") {
    return undefined;
  }

  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
}

function queueAudioChunkSend({
  blob,
  chunkSendQueueRef,
  socketRef,
  turnId,
}: {
  blob: Blob;
  chunkSendQueueRef: MutableRefObject<Promise<void>>;
  socketRef: MutableRefObject<WebSocket | null>;
  turnId: number;
}) {
  const nextSend = chunkSendQueueRef.current
    .catch(() => undefined)
    .then(async () => {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        return;
      }

      const audio = await blobToBase64(blob);
      socket.send(
        JSON.stringify({
          type: "audio_chunk",
          turnId,
          audio,
        })
      );
    });

  chunkSendQueueRef.current = nextSend;
  return nextSend;
}

function stopStreamedMediaRecorder({
  chunkSendQueueRef,
  mediaRecorder,
  peakInputLevel,
  sendInputEnd = true,
  socketRef,
  speechActiveMs,
  turnId,
}: {
  chunkSendQueueRef: MutableRefObject<Promise<void>>;
  mediaRecorder: MediaRecorder;
  peakInputLevel?: number;
  sendInputEnd?: boolean;
  socketRef: MutableRefObject<WebSocket | null>;
  speechActiveMs?: number;
  turnId: number;
}) {
  return new Promise<void>((resolve, reject) => {
    mediaRecorder.onstop = () => {
      chunkSendQueueRef.current
        .catch(() => undefined)
        .then(() => {
          const socket = socketRef.current;
          if (sendInputEnd && socket?.readyState === WebSocket.OPEN) {
            socket.send(
              JSON.stringify({
                type: "input_end",
                turnId,
                peakInputLevel,
                speechActiveMs,
              })
            );
          }
          resolve();
        })
        .catch(reject);
    };

    mediaRecorder.onerror = () => {
      reject(new Error("MediaRecorder failed"));
    };

    mediaRecorder.stop();
  });
}

function startAudioMonitoring({
  activeInputTurnIdRef,
  analyserDataRef,
  analyserNodeRef,
  audioContextRef,
  autoStopInFlightRef,
  listeningStartedAtRef,
  mediaSourceNodeRef,
  onLevel,
  onEndpoint,
  pauseToleranceSecondsRef,
  peakInputLevelRef,
  silenceCheckFrameRef,
  speechActiveMsRef,
  speechDetectedRef,
  lastMonitorAtRef,
  lastSpeechAtRef,
  stream,
  turnId,
}: {
  activeInputTurnIdRef: MutableRefObject<number | null>;
  analyserDataRef: MutableRefObject<Float32Array<ArrayBuffer> | null>;
  analyserNodeRef: MutableRefObject<AnalyserNode | null>;
  audioContextRef: MutableRefObject<AudioContext | null>;
  autoStopInFlightRef: MutableRefObject<boolean>;
  listeningStartedAtRef: MutableRefObject<number>;
  mediaSourceNodeRef: MutableRefObject<MediaStreamAudioSourceNode | null>;
  onLevel: (value: number) => void;
  onEndpoint: () => void;
  pauseToleranceSecondsRef: MutableRefObject<number>;
  peakInputLevelRef: MutableRefObject<number>;
  silenceCheckFrameRef: MutableRefObject<number | null>;
  speechActiveMsRef: MutableRefObject<number>;
  speechDetectedRef: MutableRefObject<boolean>;
  lastMonitorAtRef: MutableRefObject<number>;
  lastSpeechAtRef: MutableRefObject<number>;
  stream: MediaStream;
  turnId: number;
}) {
  if (Platform.OS !== "web" || typeof window === "undefined") {
    return;
  }

  const AudioContextCtor =
    window.AudioContext ||
    // @ts-expect-error Safari legacy prefix.
    window.webkitAudioContext;

  if (!AudioContextCtor) {
    return;
  }

  stopAudioMonitoring({
    analyserNodeRef,
    audioContextRef,
    mediaSourceNodeRef,
    silenceCheckFrameRef,
  });

  const audioContext = new AudioContextCtor();
  const source = audioContext.createMediaStreamSource(stream);
  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.82;
  source.connect(analyser);

  audioContextRef.current = audioContext;
  mediaSourceNodeRef.current = source;
  analyserNodeRef.current = analyser;
  analyserDataRef.current = new Float32Array(
    analyser.fftSize
  ) as unknown as Float32Array<ArrayBuffer>;

  const minimumTurnDurationMs = 550;
  const levelThreshold = 0.022;

  const tick = () => {
    if (
      activeInputTurnIdRef.current !== turnId ||
      useAgentStore.getState().conversationState !== "listening" ||
      !analyserNodeRef.current ||
      !analyserDataRef.current
    ) {
      return;
    }

    const analyserBuffer = analyserDataRef.current;
    analyserNodeRef.current.getFloatTimeDomainData(analyserBuffer);
    let sumSquares = 0;
    for (const sample of analyserDataRef.current) {
      sumSquares += sample * sample;
    }

    const rms = Math.sqrt(sumSquares / analyserDataRef.current.length);
    const now = performance.now();
    const deltaMs = Math.min(Math.max(now - lastMonitorAtRef.current, 0), 50);
    lastMonitorAtRef.current = now;
    const normalizedLevel = Math.max(0, Math.min(1, (rms - 0.008) / 0.072));
    peakInputLevelRef.current = Math.max(peakInputLevelRef.current, normalizedLevel);
    onLevel(normalizedLevel);

    if (rms >= levelThreshold) {
      speechActiveMsRef.current += deltaMs;
      lastSpeechAtRef.current = now;

      if (
        speechActiveMsRef.current >= MINIMUM_SPEECH_ACTIVE_MS &&
        peakInputLevelRef.current >= MINIMUM_SPEECH_PEAK_LEVEL
      ) {
        speechDetectedRef.current = true;
      }
    }

    const pauseToleranceMs = Math.max(650, pauseToleranceSecondsRef.current * 1000);
    const silenceDuration = now - lastSpeechAtRef.current;
    const timeSinceStart = now - listeningStartedAtRef.current;

    if (
      speechDetectedRef.current &&
      !autoStopInFlightRef.current &&
      timeSinceStart >= minimumTurnDurationMs &&
      silenceDuration >= pauseToleranceMs
    ) {
      onEndpoint();
      return;
    }

    silenceCheckFrameRef.current = window.requestAnimationFrame(tick);
  };

  silenceCheckFrameRef.current = window.requestAnimationFrame(tick);
}

function stopAudioMonitoring({
  analyserNodeRef,
  audioContextRef,
  mediaSourceNodeRef,
  silenceCheckFrameRef,
}: {
  analyserNodeRef: MutableRefObject<AnalyserNode | null>;
  audioContextRef: MutableRefObject<AudioContext | null>;
  mediaSourceNodeRef: MutableRefObject<MediaStreamAudioSourceNode | null>;
  silenceCheckFrameRef: MutableRefObject<number | null>;
}) {
  if (Platform.OS !== "web" || typeof window === "undefined") {
    return;
  }

  if (silenceCheckFrameRef.current !== null) {
    window.cancelAnimationFrame(silenceCheckFrameRef.current);
    silenceCheckFrameRef.current = null;
  }

  try {
    mediaSourceNodeRef.current?.disconnect();
  } catch {}

  try {
    analyserNodeRef.current?.disconnect();
  } catch {}

  mediaSourceNodeRef.current = null;
  analyserNodeRef.current = null;

  const audioContext = audioContextRef.current;
  audioContextRef.current = null;
  if (audioContext) {
    void audioContext.close().catch(() => undefined);
  }
}

function blobToBase64(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Unexpected FileReader result"));
        return;
      }

      const [, base64 = ""] = result.split(",");
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read blob"));
    reader.readAsDataURL(blob);
  });
}

function speakFallback(
  text: string,
  playbackToken: number,
  playbackTokenRef: MutableRefObject<number>,
  onComplete: () => void,
  cancelExisting = true
) {
  if (Platform.OS === "web" && typeof window !== "undefined" && "speechSynthesis" in window) {
    const synth = window.speechSynthesis;
    if (cancelExisting) {
      synth.cancel();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    const voice = chooseBestWebVoice(synth.getVoices());
    if (voice) {
      utterance.voice = voice;
    }

    utterance.rate = 0.94;
    utterance.pitch = 1.0;
    utterance.volume = 1;
    utterance.onend = () => {
      if (playbackTokenRef.current === playbackToken) {
        onComplete();
      }
    };
    utterance.onerror = () => {
      if (playbackTokenRef.current === playbackToken) {
        onComplete();
      }
    };

    if (!voice) {
      const handleVoicesChanged = () => {
        const loadedVoice = chooseBestWebVoice(synth.getVoices());
        if (loadedVoice) {
          utterance.voice = loadedVoice;
        }
        if (playbackTokenRef.current === playbackToken) {
          synth.speak(utterance);
        }
        synth.removeEventListener("voiceschanged", handleVoicesChanged);
      };

      synth.addEventListener("voiceschanged", handleVoicesChanged);
      setTimeout(() => {
        synth.removeEventListener("voiceschanged", handleVoicesChanged);
        if (playbackTokenRef.current === playbackToken) {
          synth.speak(utterance);
        }
      }, 150);
      return;
    }

    synth.speak(utterance);
    return;
  }

  Speech.speak(text, {
    rate: 0.95,
    pitch: 1.0,
    onDone: () => {
      if (playbackTokenRef.current === playbackToken) {
        onComplete();
      }
    },
    onStopped: () => {
      if (playbackTokenRef.current === playbackToken) {
        onComplete();
      }
    },
    onError: () => {
      if (playbackTokenRef.current === playbackToken) {
        onComplete();
      }
    },
  });
}

function chooseBestWebVoice(voices: SpeechSynthesisVoice[]) {
  const preferredVoiceNames = [
    "Samantha",
    "Ava",
    "Allison",
    "Google UK English Female",
    "Microsoft Aria Online (Natural)",
    "Karen",
    "Moira",
  ];

  for (const name of preferredVoiceNames) {
    const directMatch = voices.find((voice) => voice.name === name);
    if (directMatch) {
      return directMatch;
    }
  }

  return (
    voices.find(
      (voice) =>
        voice.lang.toLowerCase().startsWith("en") &&
        /female|natural|samantha|ava|allison|aria|karen|moira/i.test(voice.name)
    ) ??
    voices.find((voice) => voice.lang.toLowerCase().startsWith("en")) ??
    null
  );
}
