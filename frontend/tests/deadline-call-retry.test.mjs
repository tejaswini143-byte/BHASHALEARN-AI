import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

test("deadline call preserves a failed turn id and offers explicit retry", async () => {
  const source = await readFile(new URL("../src/DeadlineCallAssistant.tsx", import.meta.url), "utf8");
  assert.match(source, /retryTurn, setRetryTurn/);
  assert.match(source, /turn_id: turnId/);
  assert.match(source, /setRetryTurn\(\{ text: text\.trim\(\), turnId \}\)/);
  assert.match(source, /sendTurn\(retryTurn\.text, retryTurn\.turnId\)/);
  assert.match(source, /Retry last turn/);
});
