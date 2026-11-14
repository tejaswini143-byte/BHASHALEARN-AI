export interface DesktopExecutionGate {
  enable(): void;
  disable(): void;
  snapshot(): number;
  registerPlan(planId: string): void;
  invalidatePlan(): void;
  begin(planId: string): number;
  finish(token: number): void;
  isCurrent(token: number): boolean;
  assertCurrent(token: number): void;
}

export function createDesktopExecutionGate(): DesktopExecutionGate;
