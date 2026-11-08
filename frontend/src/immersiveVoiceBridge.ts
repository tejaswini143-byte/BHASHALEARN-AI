import type { AvatarSyncFrame } from "./avatarSync";

export type ImmersiveVoiceState = "idle" | "listening" | "thinking" | "speaking" | "paused" | "interrupted" | "error";
const silentFrame: AvatarSyncFrame = { generation: 0, state: "idle", mode: "silent", language: "mixed", currentTimeMs: 0, viseme: "sil" };

/** Stable event and media-clock contract for the immersive teacher renderer. */
export class ImmersiveVoiceBridge {
  private state: ImmersiveVoiceState = "idle";
  private frame: AvatarSyncFrame = { ...silentFrame };
  private latestGeneration = 0;
  private listeners = new Set<() => void>();
  private frameListeners = new Set<() => void>();
  getState = (): ImmersiveVoiceState => this.state;
  getFrame = (): AvatarSyncFrame => this.frame;
  subscribe = (listener: () => void): (() => void) => { this.listeners.add(listener); return () => this.listeners.delete(listener); };
  subscribeFrames = (listener: () => void): (() => void) => { this.frameListeners.add(listener); return () => this.frameListeners.delete(listener); };
  setState(state: ImmersiveVoiceState): void {
    if (state === this.state) return;
    this.state = state;
    if (state !== "speaking") this.frame = { ...this.frame, viseme: "sil" };
    this.listeners.forEach(listener => listener());
  }
  acceptFrame(frame: AvatarSyncFrame): void {
    if (frame.generation < this.latestGeneration) return;
    this.latestGeneration = frame.generation;
    this.frame = { ...frame };
    this.frameListeners.forEach(listener => listener());
    const state: ImmersiveVoiceState = frame.state === "playing" ? "speaking"
      : frame.state === "paused" ? "paused"
        : frame.state === "interrupted" ? "interrupted"
          : frame.state === "error" ? "error" : "idle";
    this.setState(state);
  }
  clear(): void {
    this.latestGeneration = 0;
    this.frame = { ...silentFrame };
    this.frameListeners.forEach(listener => listener());
    this.setState("idle");
  }
}

export const immersiveVoiceBridge = new ImmersiveVoiceBridge();
