import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
require.extensions[".tsx"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
require.extensions[".css"] = () => {};
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const model = require(resolve(root, "src/futureMeModel.ts"));
const { FutureMeSimulator } = require(resolve(root, "src/FutureMeSimulator.tsx"));

test("career selection starts a deterministic local scenario", () => {
  assert.deepEqual(model.careerScenarios.map(item => item.id), ["software-engineer", "doctor", "scientist", "entrepreneur"]);
  const state = model.startSimulation("scientist");
  assert.equal(state.careerId, "scientist");
  assert.equal(state.stepIndex, 0);
  assert.equal(model.isSimulationComplete(state), false);
});

test("scenario branches produce different consequences and skill outcomes", () => {
  const start = model.startSimulation("software-engineer");
  const investigate = model.chooseScenarioOption(start, "reproduce");
  const workaround = model.chooseScenarioOption(start, "patch");
  assert.equal(investigate.stepIndex, 1);
  assert.notEqual(investigate.choices[0].outcome, workaround.choices[0].outcome);
  assert.match(investigate.choices[0].explanation, /evidence/);
  assert.ok(model.demonstratedSkills(investigate).includes("Debugging"));
  assert.equal(model.chooseScenarioOption(start, "missing-choice"), start);
});

test("scenario completion follows selected decisions and returns demonstrated skills", () => {
  let state = model.startSimulation("doctor");
  for (const id of ["listen", "summarize", "plain"]) state = model.chooseScenarioOption(state, id);
  assert.equal(model.isSimulationComplete(state), true);
  assert.deepEqual(model.demonstratedSkills(state), ["Active listening", "Empathy", "Clear communication", "Attention to detail", "Teaching"]);
  assert.equal(model.chooseScenarioOption(state, "plain"), state);
});

test("career picker exposes labeled keyboard-operable choices and prediction disclaimer", async () => {
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(FutureMeSimulator)));
  assert.match(html, /Just an illustration/);
  assert.match(html, /do not predict your future/);
  for (const career of ["Software engineer", "Doctor", "Scientist", "Entrepreneur"]) assert.match(html, new RegExp(`>${career}<`));
  assert.equal((html.match(/<button/g) || []).length, 4);
  const css = await readFile(resolve(root, "src/future-me.css"), "utf8");
  assert.match(css, /:focus-visible/);
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.match(css, /@media\(max-width:650px\)/);
});

test("dedicated route is registered", async () => {
  const app = await readFile(resolve(root, "src/App.tsx"), "utf8");
  assert.match(app, /path="\/future-me" element=\{<FutureMeSimulator\/>\}/);
  assert.match(app, /from "\.\/FutureMeSimulator"/);
});
