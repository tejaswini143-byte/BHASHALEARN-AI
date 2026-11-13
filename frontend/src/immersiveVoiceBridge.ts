import type { AvatarSyncFrame } from "./avatarSync";

export type ImmersiveVoiceState = "idle" | "listening" | "thinking" | "speaking" | "paused" | "interrupted" | "error";

const silentFrame: AvatarSyncFrame = { generation: 0, state: "idle", mode: "silent", language: "mixed", currentTimeMs: 0, viseme: "sil" };

/** Stable bridge between VoiceTutor's media-clock controller and any avatar renderer. */
export class ImmersiveVoiceBridge {
  private state: ImmersiveVoiceState = "idle";
  private frame: AvatarSyncFrame = { ...silentFrame };
  private latestGeneration = 0;
  private listeners = new Set<() => void>();
  private frameListeners = new Set<() => void>();

  getState = (): ImmersiveVoiceState => this.state;
  getFrame = (): AvatarSyncFrame => this.frame;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
  subscribeFrames = (listener: () => void): (() => void) => {
    this.frameListeners.add(listener);
    return () => this.frameListeners.delete(listener);
  };

  setState(state: ImmersiveVoiceState): void {
    if (state === this.state) return;
    this.state = state;
    if (state !== "speaking") {
      this.frame = { ...this.frame, viseme: "sil" };
      this.frameListeners.forEach(listener => listener());
    }
    this.emit();
  }

  acceptFrame(frame: AvatarSyncFrame): void {
    if (!Number.isSafeInteger(frame.generation) || frame.generation < this.latestGeneration || frame.generation === 0) return;
    if (!Number.isFinite(frame.currentTimeMs) || frame.currentTimeMs < 0) return;
    this.latestGeneration = frame.generation;
    this.frame = { ...frame };
    this.frameListeners.forEach(listener => listener());
    const state: ImmersiveVoiceState = frame.state === "playing" ? "speaking"
      : frame.state === "paused" ? "paused"
        : frame.state === "interrupted" ? "interrupted"
          : frame.state === "error" ? "error" : "idle";
    if (state !== this.state) {
      this.state = state;
      this.emit();
    }
  }

  clear(): void {
    // Preserve the generation watermark so a late frame from an interrupted
    // playback cannot reactivate the avatar after a clear/unmount.
    this.frame = { ...silentFrame, generation: this.latestGeneration };
    this.frameListeners.forEach(listener => listener());
    if (this.state !== "idle") {
      this.state = "idle";
      this.emit();
    }
  }

  private emit(): void { this.listeners.forEach(listener => listener()); }
}

export const immersiveVoiceBridge = new ImmersiveVoiceBridge();
