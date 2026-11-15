import { validateVisemeTimeline, visemeAt, type Viseme, type VisemeFrame } from "./teacherCore";

export type SyncLanguage = "english" | "telugu" | "mixed";
export type SyncMode = "timestamped-visemes" | "timestamped-phonemes-approximate" | "audio-driven-approximate" | "silent";
export type SyncState = "idle" | "playing" | "paused" | "completed" | "interrupted" | "error";
export type PlaybackSnapshot = { currentTime: number; paused: boolean; ended: boolean; duration?: number };
export type AvatarSyncFrame = {
  generation: number;
  state: SyncState;
  mode: SyncMode;
  language: SyncLanguage;
  currentTimeMs: number;
  viseme: Viseme;
};
export type PhonemeFrame = { atMs: number; durationMs: number; phoneme: string };
export type SyncAudio = { visemes?: VisemeFrame[]; phonemes?: PhonemeFrame[] };

/** Reusable adapter boundary: snapshots come from the actual media element clock. */
export class AvatarSyncController {
  private generation = 0;
  private state: SyncState = "idle";
  private mode: SyncMode = "silent";
  private language: SyncLanguage = "english";
  private timeline: VisemeFrame[] = [];
  private phonemes: PhonemeFrame[] = [];
  private frame: AvatarSyncFrame;

  constructor(private readonly onFrame: (frame: AvatarSyncFrame) => void) {
    this.frame = { generation: 0, state: "idle", mode: "silent", language: this.language, currentTimeMs: 0, viseme: "sil" };
  }

  begin(audio: SyncAudio, language: SyncLanguage): number {
    // Validate before changing the active playback generation or state.
    if (!["english", "telugu", "mixed"].includes(language)) throw new Error("Invalid sync language");
    const timeline = audio.visemes?.length ? validateVisemeTimeline(audio.visemes) : [];
    const phonemes = audio.phonemes?.length ? validatePhonemeTimeline(audio.phonemes) : [];
    this.generation += 1;
    this.language = language;
    this.timeline = timeline;
    this.phonemes = phonemes;
    this.mode = this.timeline.length ? "timestamped-visemes" : this.phonemes.length ? "timestamped-phonemes-approximate" : "audio-driven-approximate";
    this.state = "idle";
    this.publish(0, "sil");
    return this.generation;
  }

  play(generation: number): void { this.changeState(generation, "playing"); }
  pause(generation: number): void { this.changeState(generation, "paused"); }
  complete(generation: number): void { this.changeState(generation, "completed"); }
  fail(generation: number): void { this.changeState(generation, "error"); }
  interrupt(generation: number): void { this.changeState(generation, "interrupted"); }

  /**
   * Call from an animation frame. Time is always sourced from media.currentTime;
   * audioLevel is optional RMS amplitude in [0, 1] from a playback-only analyser.
   */
  tick(generation: number, media: PlaybackSnapshot, audioLevel?: number): void {
    if (!this.isCurrent(generation) || this.state !== "playing") return;
    if (media.ended) { this.complete(generation); return; }
    if (media.paused || !Number.isFinite(media.currentTime) || media.currentTime < 0) return;
    const timeMs = media.currentTime * 1000;
    const viseme = this.timeline.length
      ? visemeAt(this.timeline, timeMs)
      : this.phonemes.length ? phonemeVisemeAt(this.phonemes, timeMs, this.language) : approximateViseme(this.language, timeMs, audioLevel);
    this.publish(timeMs, viseme);
  }

  cancel(generation?: number): void {
    if (generation !== undefined && !this.isCurrent(generation)) return;
    this.generation += 1;
    this.state = "interrupted";
    this.publish(0, "sil");
  }

  currentGeneration(): number { return this.generation; }
  currentState(): SyncState { return this.state; }

  private isCurrent(generation: number): boolean { return generation === this.generation; }
  private changeState(generation: number, state: SyncState): void {
    if (!this.isCurrent(generation)) return;
    this.state = state;
    this.publish(this.frame.currentTimeMs, "sil");
  }
  private publish(currentTimeMs: number, viseme: Viseme): void {
    this.frame = { generation: this.generation, state: this.state, mode: this.mode, language: this.language, currentTimeMs, viseme };
    this.onFrame({ ...this.frame });
  }
}

function validatePhonemeTimeline(timeline: PhonemeFrame[]): PhonemeFrame[] {
  let previousEnd = 0;
  for (const cue of timeline) {
    if (!Number.isFinite(cue.atMs) || cue.atMs < 0 || cue.atMs < previousEnd || !Number.isFinite(cue.durationMs) || cue.durationMs <= 0 || typeof cue.phoneme !== "string" || !cue.phoneme.trim()) {
      throw new Error("Invalid phoneme timeline");
    }
    previousEnd = cue.atMs + cue.durationMs;
    if (!Number.isSafeInteger(previousEnd)) throw new Error("Invalid phoneme timeline");
  }
  return timeline.map(cue => ({ ...cue }));
}

function phonemeVisemeAt(timeline: PhonemeFrame[], timeMs: number, language: SyncLanguage): Viseme {
  const cue = timeline.find(item => timeMs >= item.atMs && timeMs < item.atMs + item.durationMs);
  if (!cue) return "sil";
  const symbol = cue.phoneme.toLowerCase();
  if (/^[pbm]$/.test(symbol) || /[మమ్]$/.test(symbol)) return "mm";
  if (/^[fv]$/.test(symbol) || /[ఫవ]$/.test(symbol)) return "fv";
  if (/^[θð]$/.test(symbol) || /[తథదధ]$/.test(symbol)) return "th";
  if (/^[ieɪɛ]$/.test(symbol) || /[ఇఈఎఏ]$/.test(symbol)) return "ee";
  if (/^[uouɔ]$/.test(symbol) || /[ఉఊఒఓ]$/.test(symbol)) return "oh";
  if (/^[aɑæɐ]$/.test(symbol) || /[అఆఐఔ]$/.test(symbol)) return "aa";
  return language === "telugu" ? "oh" : "sil";
}

/** Coarse amplitude-to-mouth heuristics. These are not phoneme recognition or lip-sync. */
function approximateViseme(language: SyncLanguage, timeMs: number, level?: number): Viseme {
  if (level === undefined || !Number.isFinite(level)) {
    // If Web Audio analysis is unavailable, keep a conservative time-based fallback
    // driven by HTMLMediaElement.currentTime rather than a competing wall clock.
    const phase = Math.floor(timeMs / 135) % 6;
    if (phase === 0 || phase === 5) return "sil";
    if (language === "telugu") return phase % 2 ? "aa" : "oh";
    if (language === "mixed") return phase % 2 ? "ee" : "aa";
    return phase % 2 ? "ee" : "oh";
  }
  if (level < 0.018) return "sil";
  const phase = Math.floor(timeMs / 115) % 4;
  if (language === "telugu") {
    if (level < 0.075) return phase % 2 ? "mm" : "th";
    if (level < 0.2) return phase % 2 ? "oh" : "ee";
    return phase % 3 ? "aa" : "oh";
  }
  if (language === "mixed") {
    if (level < 0.075) return phase % 2 ? "mm" : "fv";
    if (level < 0.2) return phase % 2 ? "ee" : "oh";
    return phase % 3 ? "aa" : "ee";
  }
  if (level < 0.075) return phase % 2 ? "mm" : "fv";
  if (level < 0.2) return phase % 2 ? "ee" : "oh";
  return phase % 3 ? "aa" : "oh";
}
