export interface DesktopExecutionGate {
  enable(): void;
  disable(): void;
  snapshot(): number;
  begin(): number;
  isCurrent(token: number): boolean;
  assertCurrent(token: number): void;
}

export function createDesktopExecutionGate(): DesktopExecutionGate;
