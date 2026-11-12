export function createDesktopExecutionGate() {
  let generation = 0;
  let enabled = false;

  return Object.freeze({
    enable() { enabled = true; generation += 1; },
    disable() { enabled = false; generation += 1; },
    snapshot() { return generation; },
    begin() {
      if (!enabled) throw new Error("Desktop control is disabled.");
      generation += 1;
      return generation;
    },
    isCurrent(token) { return enabled && token === generation; },
    assertCurrent(token) {
      if (!enabled || token !== generation) throw new Error("Emergency Stop cancelled the remaining desktop workflow.");
    },
  });
}
