import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
require.extensions[".tsx"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
require.extensions[".css"] = () => {};
const pages = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/StudentScreens.tsx"));

test("timeline route renders its loading state and is backed by authenticated analytics", async () => {
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(pages.LearningTimelinePage)));
  assert.match(html, /Learning timeline/);
  assert.match(html, /Loading your timeline/);
  const source = await readFile(new URL("../src/StudentScreens.tsx", import.meta.url), "utf8");
  assert.match(source, /\/analytics\?range_days=7/);
  assert.match(source, /Authorization: `Bearer \$\{getToken\(\)\}`/);
  assert.match(source, /Your recorded sessions and practice activity will appear here/);
});

test("settings loads and persists profile plus learning preferences", async () => {
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(pages.SettingsPage)));
  assert.match(html, /Settings/);
  assert.match(html, /Loading your settings/);
  const source = await readFile(new URL("../src/StudentScreens.tsx", import.meta.url), "utf8");
  assert.match(source, /method: "PATCH"[\s\S]*display_name/);
  assert.match(source, /method: "PUT"[\s\S]*preferred_language/);
  assert.match(source, /Your settings are saved to your account/);
});

test("certificate eligibility comes only from completed account courses", async () => {
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(pages.CertificatePage)));
  assert.match(html, /Checking course completion/);
  const source = await readFile(new URL("../src/StudentScreens.tsx", import.meta.url), "utf8");
  assert.match(source, /\/courses\/catalog/);
  assert.match(source, /courses\.filter\(course => course\.completed\)/);
  assert.match(source, /No certificates yet/);
  assert.match(source, /window\.print\(\)/);
});

test("recovery and student screen routes are registered", async () => {
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");
  for (const path of ["/forgot-password", "/reset-password", "/timeline", "/settings", "/certificate"]) assert.ok(app.includes(`path="${path}"`), `missing ${path}`);
  const authPages = await readFile(new URL("../src/AuthPages.tsx", import.meta.url), "utf8");
  assert.match(authPages, /password-reset\/request/);
  assert.match(authPages, /password-reset\/complete/);
  assert.match(authPages, /Passwords do not match/);
});
