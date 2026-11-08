import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

test("research workspace exposes bilingual controls, citations, and explicit non-execution", async () => {
  const component = await readFile(new URL("../src/ResearchWorkspace.tsx", import.meta.url), "utf8");
  const css = await readFile(new URL("../src/research.css", import.meta.url), "utf8");
  assert.match(component, /value="telugu">తెలుగు/);
  assert.match(component, /OFFLINE DEMONSTRATION · FIXTURE SOURCES/);
  assert.match(component, /canonical_url/);
  assert.match(component, /AI interpretation based on the cited excerpts/);
  assert.match(component, /Browser execution and external actions are unavailable/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /max-width:720px/);
});
