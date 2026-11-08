import { validateTeacherAction, type BoardTarget, type TeacherAction, type VisemeFrame } from "./teacherCore";
import type { AvatarSyncFrame } from "./avatarSync";

export type VoiceLanguage = "english" | "telugu" | "mixed";

export type VoiceErrorCode =
  | "permission_denied"
  | "unsupported"
  | "no_speech"
  | "network"
  | "provider"
  | "invalid_audio"
  | "interrupted";

export type VoiceError = {
  code: VoiceErrorCode;
  message: string;
  retryable: boolean;
};

export type RecognitionEvent =
  | { type: "recognition_started" }
  | { type: "transcript_partial"; text: string; language?: string }
  | { type: "transcript_final"; text: string; language?: string }
  | { type: "recognition_failed"; error: VoiceError };

export type SpeechEvent =
  | { type: "synthesis_started" }
  | { type: "audio_ready"; audio: SpeechAudio }
  | { type: "playback_started" }
  | { type: "playback_ended" }
  | { type: "playback_interrupted" }
  | { type: "synthesis_failed"; error: VoiceError };

export type SpeechAudio = {
  url: string;
  contentType: "audio/wav";
  /** Only populated when the provider or alignment service supplies timing. */
  durationMs?: number;
  visemes?: VisemeFrame[];
  /** Optional timestamped phoneme labels from a real alignment source; not emitted by current Timbre REST. */
  phonemes?: Array<{ atMs: number; durationMs: number; phoneme: string }>;
};

export type RecognitionRequest = {
  sessionId: string;
  language: VoiceLanguage;
  audio: Blob;
};

export type SpeechRequest = {
  sessionId: string;
  language: VoiceLanguage;
  text: string;
};

/** Provider-neutral contract. Current Prisma/Timbre implementations use bounded REST calls. */
export interface VoiceTransport {
  recognize(request: RecognitionRequest, signal?: AbortSignal): AsyncIterable<RecognitionEvent>;
  synthesize(request: SpeechRequest, signal?: AbortSignal): AsyncIterable<SpeechEvent>;
}

export type TeacherVoiceEvent =
  | { type: "playback_started"; audio: SpeechAudio }
  | { type: "playback_ended" }
  | { type: "playback_interrupted" }
  | { type: "smartboard_command"; action: Extract<TeacherAction, { type: "pointAt" }> };

export type TeacherIntegrationCommand =
  | { type: "teacher_state"; state: "explain" | "idle" }
  | { type: "teacher_action"; action: TeacherAction };

/** Maps audio playback onto ADV-05 states/actions; absent visemes stay silent. */
export function teacherActionsForVoiceEvent(event: TeacherVoiceEvent): TeacherIntegrationCommand[] {
  switch (event.type) {
    case "playback_started": {
      const commands: TeacherIntegrationCommand[] = [{ type: "teacher_state", state: "explain" }];
      if (event.audio.visemes?.length) commands.push({ type: "teacher_action", action: validateTeacherAction({ type: "speak", timeline: event.audio.visemes }) });
      return commands;
    }
    case "playback_ended":
    case "playback_interrupted":
      return [{ type: "teacher_state", state: "idle" }];
    case "smartboard_command":
      return [{ type: "teacher_action", action: validateTeacherAction(event.action) }];
  }
}

/** Narrow bridge from controller samples to the existing ADV-05 teacher actions. */
export function teacherActionsForAvatarSyncFrame(frame: AvatarSyncFrame): TeacherIntegrationCommand[] {
  if (frame.state !== "playing") return [{ type: "teacher_state", state: "idle" }];
  const commands: TeacherIntegrationCommand[] = [{ type: "teacher_state", state: "explain" }];
  if (frame.viseme !== "sil") commands.push({
    type: "teacher_action",
    action: validateTeacherAction({ type: "speak", timeline: [{ atMs: 0, durationMs: 120, viseme: frame.viseme }] }),
  });
  return commands;
}

/** Deterministic development double. It emits exact Telugu/English text and a tiny mock WAV URL. */
export class MockVoiceTransport implements VoiceTransport {
  constructor(
    private readonly transcript = "\u0C28\u0C2E\u0C38\u0C4D\u0C15\u0C3E\u0C30\u0C02! Hello, let us learn fractions.",
    private readonly audioUrl = "mock://timbre/reply.wav",
  ) {}

  async *recognize(_request: RecognitionRequest, signal?: AbortSignal): AsyncIterable<RecognitionEvent> {
    if (signal?.aborted) {
      yield { type: "recognition_failed", error: { code: "interrupted", message: "Recognition was cancelled.", retryable: true } };
      return;
    }
    yield { type: "recognition_started" };
    yield { type: "transcript_partial", text: this.transcript.slice(0, Math.ceil(this.transcript.length / 2)) };
    yield { type: "transcript_final", text: this.transcript, language: "te-en" };
  }

  async *synthesize(_request: SpeechRequest, signal?: AbortSignal): AsyncIterable<SpeechEvent> {
    if (signal?.aborted) {
      yield { type: "synthesis_failed", error: { code: "interrupted", message: "Synthesis was cancelled.", retryable: true } };
      return;
    }
    yield { type: "synthesis_started" };
    yield { type: "audio_ready", audio: { url: this.audioUrl, contentType: "audio/wav" } };
  }
}

export function normalizedBoardCommand(target: BoardTarget): TeacherVoiceEvent {
  return { type: "smartboard_command", action: validateTeacherAction({ type: "pointAt", target }) as Extract<TeacherAction, { type: "pointAt" }> };
}
