// ═══════════════════════════════════════════════════════════════
// NEXUS — Voice UI Components
// VoiceButton, VoiceWaveform, TTSPlayback
// Web Audio API recording, transcription, and TTS playback
// ═══════════════════════════════════════════════════════════════

"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNexusStore } from "@/lib/nexus-store";
import { nexusApi } from "@/lib/nexus-api";
import { Mic, MicOff, Loader2, Volume2, VolumeX } from "lucide-react";
import { createLogger } from "@/lib/logger";

const logger = createLogger("voice-ui");

// ── VoiceWaveform ───────────────────────────────────────────
// Small animated waveform visualization using CSS animations
// Shows when recording or playing

export function VoiceWaveform({
  active = true,
  barCount = 7,
  className = "",
}: {
  active?: boolean;
  barCount?: number;
  className?: string;
}) {
  // Generate deterministic delays for bars
  const barConfigs = Array.from({ length: barCount }, (_, i) => ({
    delay: i * 0.08,
    minHeight: 4 + Math.abs(i - Math.floor(barCount / 2)) * 2,
    maxHeight: 16 + (barCount - Math.abs(i - Math.floor(barCount / 2))) * 3,
  }));

  return (
    <div className={`flex items-center justify-center gap-[3px] h-6 ${className}`}>
      {barConfigs.map((bar, i) => (
        <motion.div
          key={i}
          className="w-[3px] rounded-full bg-current"
          initial={{ height: bar.minHeight }}
          animate={
            active
              ? {
                  height: [bar.minHeight, bar.maxHeight, bar.minHeight],
                }
              : { height: bar.minHeight }
          }
          transition={
            active
              ? {
                  duration: 0.5 + i * 0.05,
                  repeat: Infinity,
                  ease: "easeInOut",
                  delay: bar.delay,
                }
              : { duration: 0.3 }
          }
        />
      ))}
    </div>
  );
}

// ── TTSPlayback ─────────────────────────────────────────────
// Plays TTS audio when a chat message comes in
// Updates avatar visemes for lip-sync
// Can be toggled on/off in settings

export function TTSPlayback({
  text,
  onPlayStart,
  onPlayEnd,
}: {
  text: string;
  onPlayStart?: () => void;
  onPlayEnd?: () => void;
}) {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const blobUrlRef = useRef<string | null>(null);
  const { setVoiceState, setCurrentVisemes } = useNexusStore();

  const speak = useCallback(async () => {
    if (!text || isPlaying) return;

    try {
      setVoiceState("playing");
      setIsPlaying(true);
      onPlayStart?.();

      const voiceConfig = useNexusStore.getState().voiceConfig;
      const result = await nexusApi.voiceSynthesize(text, voiceConfig.engine, voiceConfig.voice);

      // Update visemes for lip-sync
      if (result.visemes && result.visemes.length > 0) {
        setCurrentVisemes(result.visemes);

        // Schedule viseme clearing after the last one
        const lastViseme = result.visemes[result.visemes.length - 1];
        setTimeout(() => setCurrentVisemes([]), lastViseme.end);
      }

      // Play audio
      if (result.audio) {
        const audioBytes = atob(result.audio);
        const audioArray = new Uint8Array(audioBytes.length);
        for (let i = 0; i < audioBytes.length; i++) {
          audioArray[i] = audioBytes.charCodeAt(i);
        }
        const blob = new Blob([audioArray], { type: "audio/mp3" });
        const url = URL.createObjectURL(blob);
        blobUrlRef.current = url;

        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          setIsPlaying(false);
          setVoiceState("idle");
          setCurrentVisemes([]);
          onPlayEnd?.();
          URL.revokeObjectURL(url);
        };

        audio.onerror = () => {
          setIsPlaying(false);
          setVoiceState("idle");
          setCurrentVisemes([]);
          onPlayEnd?.();
          URL.revokeObjectURL(url);
        };

        await audio.play();
      } else {
        // No audio returned, just finish
        setIsPlaying(false);
        setVoiceState("idle");
        onPlayEnd?.();
      }
    } catch {
      setIsPlaying(false);
      setVoiceState("error");
      onPlayEnd?.();
      setTimeout(() => setVoiceState("idle"), 2000);
    }
  }, [text, isPlaying, setVoiceState, setCurrentVisemes, onPlayStart, onPlayEnd]);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setIsPlaying(false);
    setVoiceState("idle");
    setCurrentVisemes([]);
    onPlayEnd?.();
  }, [setVoiceState, setCurrentVisemes, onPlayEnd]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      // Revoke blob URL to prevent memory leak
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, []);

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={isPlaying ? stop : speak}
        aria-label={isPlaying ? "Arreter la lecture" : "Lire a voix haute"}
        className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${
          isPlaying
            ? "bg-emerald-500/20 text-emerald-500 hover:bg-emerald-500/30"
            : "bg-muted/30 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
        }`}
        title={isPlaying ? "Arreter la lecture" : "Lire a voix haute"}
      >
        {isPlaying ? (
          <div className="flex items-center gap-0.5">
            <Volume2 size={11} />
            <VoiceWaveform active={isPlaying} barCount={3} className="h-3" />
          </div>
        ) : (
          <Volume2 size={11} />
        )}
      </button>
    </div>
  );
}

// ── VoiceButton ─────────────────────────────────────────────
// Floating button near the chat input
// Click to start/stop recording
// Sends audio to backend for transcription
// Receives text and puts it in the chat input

export function VoiceButton({
  onTranscription,
  className = "",
}: {
  onTranscription: (text: string) => void;
  className?: string;
}) {
  const voiceState = useNexusStore((s) => s.voiceState);
  const setVoiceState = useNexusStore((s) => s.setVoiceState);
  const setCurrentTranscription = useNexusStore((s) => s.setCurrentTranscription);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4",
      });

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }

        if (chunksRef.current.length === 0) {
          setVoiceState("idle");
          return;
        }

        // Transcribe
        setVoiceState("transcribing");

        try {
          const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
          const reader = new FileReader();

          reader.onloadend = async () => {
            const base64 = (reader.result as string).split(",")[1];
            try {
              const result = await nexusApi.voiceTranscribe(base64);
              if (result.text) {
                setCurrentTranscription(result.text);
                onTranscription(result.text);
              }
            } catch (err) {
              logger.warn("Transcription failed", err);
            } finally {
              setVoiceState("idle");
            }
          };

          reader.readAsDataURL(blob);
        } catch (err) {
          logger.error("Recording failed", err);
          setVoiceState("error");
          setTimeout(() => setVoiceState("idle"), 2000);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(250); // Collect data every 250ms
      setVoiceState("recording");
    } catch {
      // Microphone not available
      setVoiceState("error");
      setTimeout(() => setVoiceState("idle"), 2000);
    }
  }, [setVoiceState, setCurrentTranscription, onTranscription]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const handleClick = useCallback(() => {
    switch (voiceState) {
      case "idle":
        startRecording();
        break;
      case "recording":
        stopRecording();
        break;
      case "playing":
        // Stop playback handled elsewhere
        break;
      case "transcribing":
      case "error":
        // Do nothing, wait for state to resolve
        break;
    }
  }, [voiceState, startRecording, stopRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  return (
    <div className={`relative ${className}`}>
      <motion.button
        onClick={handleClick}
        aria-label={
          voiceState === "recording"
            ? "Arreter l'enregistrement"
            : voiceState === "transcribing"
            ? "Transcription en cours..."
            : "Enregistrer un message vocal"
        }
        aria-pressed={voiceState === "recording"}
        className={`relative w-9 h-9 rounded-full flex items-center justify-center transition-colors ${
          voiceState === "recording"
            ? "bg-red-500/20 text-red-500 hover:bg-red-500/30"
            : voiceState === "transcribing"
            ? "bg-amber-500/20 text-amber-500"
            : voiceState === "playing"
            ? "bg-emerald-500/20 text-emerald-500"
            : voiceState === "error"
            ? "bg-red-500/20 text-red-400"
            : "bg-muted/30 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
        }`}
        whileTap={{ scale: 0.9 }}
        title={
          voiceState === "recording"
            ? "Arreter l'enregistrement"
            : voiceState === "transcribing"
            ? "Transcription en cours..."
            : "Enregistrer un message vocal"
        }
      >
        {/* Pulsing ring when recording */}
        <AnimatePresence>
          {voiceState === "recording" && (
            <motion.div
              initial={{ scale: 1, opacity: 0.6 }}
              animate={{ scale: 1.8, opacity: 0 }}
              exit={{ scale: 1, opacity: 0 }}
              transition={{ duration: 1, repeat: Infinity, ease: "easeOut" }}
              className="absolute inset-0 rounded-full bg-red-500/40"
            />
          )}
        </AnimatePresence>

        {/* Icon based on state */}
        {voiceState === "recording" ? (
          <div className="relative z-10 flex items-center gap-1">
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
              className="w-3 h-3 rounded-full bg-red-500"
            />
          </div>
        ) : voiceState === "transcribing" ? (
          <Loader2 size={15} className="animate-spin" />
        ) : voiceState === "playing" ? (
          <Volume2 size={15} />
        ) : voiceState === "error" ? (
          <MicOff size={15} />
        ) : (
          <Mic size={15} />
        )}
      </motion.button>

      {/* Waveform overlay when recording */}
      <AnimatePresence>
        {voiceState === "recording" && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 5 }}
            className="absolute -top-8 left-1/2 -translate-x-1/2 bg-red-500/10 border border-red-500/20 rounded-lg px-2 py-1"
          >
            <VoiceWaveform active={voiceState === "recording"} barCount={5} className="text-red-500" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
