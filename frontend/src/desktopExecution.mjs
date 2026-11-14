export function createDesktopExecutionGate() {
  let generation = 0;
  let enabled = false;
  let pendingPlan = null;
  let runningToken = null;

  return Object.freeze({
    enable() { enabled = true; pendingPlan = null; generation += 1; },
    disable() { enabled = false; pendingPlan = null; generation += 1; },
    snapshot() { return generation; },
    registerPlan(planId) {
      if (!enabled) throw new Error("Desktop control is disabled.");
      if (!planId) throw new Error("A valid action plan is required.");
      pendingPlan = planId;
    },
    invalidatePlan() { pendingPlan = null; generation += 1; },
    begin(planId) {
      if (!enabled) throw new Error("Desktop control is disabled.");
      if (runningToken !== null) throw new Error("An action is already executing.");
      if (!planId || pendingPlan !== planId) throw new Error("A fresh confirmation is required for this action.");
      pendingPlan = null;
      generation += 1;
      runningToken = generation;
      return generation;
    },
    finish(token) { if (runningToken === token) runningToken = null; },
    isCurrent(token) { return enabled && token === generation; },
    assertCurrent(token) {
      if (!enabled || token !== generation) throw new Error("Emergency Stop cancelled the remaining desktop workflow.");
    },
  });
}
