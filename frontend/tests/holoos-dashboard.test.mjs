import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText, filename);
const model = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/holoosDashboardModel.ts"));

test("dashboard mastery values are finite and stay within the progress scale", () => {
  assert.equal(model.clampMastery(72.4), 72.4);
  assert.equal(model.clampMastery(-5), 0);
  assert.equal(model.clampMastery(140), 100);
  assert.equal(model.clampMastery(Number.NaN), 0);
});

test("dashboard labels handle empty names, invalid dates, and case-insensitive session search", () => {
  assert.equal(model.firstName("  Tejaswini Rao  "), "Tejaswini");
  assert.equal(model.firstName("  "), "there");
  assert.equal(model.formatSessionDate("invalid"), "Date unavailable");
  assert.equal(model.matchesSession("Fractions in Telugu", "  telugu "), true);
  assert.equal(model.matchesSession("Fractions", "Decimals"), false);
});
