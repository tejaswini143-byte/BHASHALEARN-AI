import type { ReactNode } from "react";

/** Presentation contracts for feature workstreams. Optional entries render only when a caller marks them available. */
export type IntegratedFeature = "int17-assistant" | "int19-teacher" | "int20-voice" | "int21-career" | "int22-command-center" | "int23-knowledge-studio" | "int24-research-agent" | "int25-communication-hub";

export function FeatureAdapter({ feature, available = false, children }: { feature: IntegratedFeature; available?: boolean; children: ReactNode }) {
  if (!available) return null;
  return <div className="holo-feature-adapter" data-feature-contract={feature}>{children}</div>;
}

export const featureContractIds: readonly IntegratedFeature[] = [
  "int17-assistant", "int19-teacher", "int20-voice", "int21-career",
  "int22-command-center", "int23-knowledge-studio", "int24-research-agent", "int25-communication-hub",
];
