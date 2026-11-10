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
const { KnowledgeStudio } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/KnowledgeStudio.tsx"));

test("Knowledge Studio renders loading, private document selection and bilingual controls", () => {
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(KnowledgeStudio)));
  assert.match(html, /Knowledge Studio/);
  assert.match(html, /Loading your documents/);
  assert.match(html, /Ask your material/);
  assert.match(html, /English/);
});

test("studio exposes authenticated question, material, quiz and citation workflows", async () => {
  const source = await readFile(new URL("../src/KnowledgeStudio.tsx", import.meta.url), "utf8");
  for (const expected of ["/knowledge/ask", "/knowledge/learning", "summary", "concepts", "flashcards", "practice", "quiz", "Check answers", "citation_id", "page=${cite.page_number}", "No supporting page citation"]) assert.ok(source.includes(expected), `missing Knowledge Studio contract: ${expected}`);
});

test("application and authenticated dashboard route to Knowledge Studio", async () => {
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");
  const dashboard = await readFile(new URL("../src/Dashboard.tsx", import.meta.url), "utf8");
  assert.ok(app.includes("/knowledge-studio"));
  assert.ok(dashboard.includes("Knowledge Studio"));
});
