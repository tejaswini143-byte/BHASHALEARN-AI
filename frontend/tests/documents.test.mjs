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
const { DocumentsPage, DocumentDetailPage } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/Documents.tsx"));
const { validatePdfSelection, createDocumentUploadBody } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/documentModel.ts"));
const { requestHeaders, request } = require(resolve(dirname(fileURLToPath(import.meta.url)), "../src/auth.ts"));

test("Documents component renders upload and library loading UI", () => {
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(DocumentsPage)));
  assert.match(html, /Documents/);
  assert.match(html, /Add a study document/);
  assert.match(html, /Upload PDF/);
  assert.match(html, /Loading your documents/);
});

test("Document details component renders loading UI", () => {
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, null, React.createElement(DocumentDetailPage)));
  assert.match(html, /Loading document/);
});

test("document component exposes upload, loading, status, and empty states", async () => {
  const source = await readFile(new URL("../src/Documents.tsx", import.meta.url), "utf8");
  for (const expected of ["Add a study document", "Browse files", "Upload PDF", "Loading your documents", "No documents yet", "role=\"alert\"", "role=\"status\"", "Your documents", "onDrop", "window.confirm"]) assert.ok(source.includes(expected), `missing UI contract: ${expected}`);
});

test("document details fetch bounded pages and display extraction results", async () => {
  const source = await readFile(new URL("../src/Documents.tsx", import.meta.url), "utf8");
  assert.match(source, /\/documents\/\$\{encodeURIComponent\(documentId\)\}\/pages\?limit=5&offset=/);
  assert.ok(source.includes("extracted_text"));
  assert.ok(source.includes("No selectable text found"));
});

test("documents UI exposes explicit indexing status and authenticated semantic search controls", async () => {
  const source = await readFile(new URL("../src/Documents.tsx", import.meta.url), "utf8");
  assert.ok(source.includes("/index-status"));
  assert.ok(source.includes("/index${"));
  assert.ok(source.includes("/documents/search"));
  assert.ok(source.includes("?force=true"));
  assert.ok(source.includes("Index document"));
  assert.ok(source.includes("Retry indexing"));
  assert.ok(source.includes("No indexed documents matched your search."));
  assert.ok(source.includes("aria-labelledby=\"semantic-search-heading\""));
  assert.ok(source.includes("Similarity"));
});

test("file selection rejects invalid, empty, and oversized files", () => {
  assert.equal(validatePdfSelection({ name: "notes.txt", type: "text/plain", size: 1 }), "Choose a PDF file.");
  assert.equal(validatePdfSelection({ name: "empty.pdf", type: "application/pdf", size: 0 }), "The selected file is empty.");
  assert.match(validatePdfSelection({ name: "large.pdf", type: "application/pdf", size: 10 * 1024 * 1024 + 1 }), /10 MB/);
  assert.equal(validatePdfSelection({ name: "lesson.pdf", type: "application/pdf", size: 20 }), null);
});

test("multipart upload body uses the backend's file field", () => {
  const blob = new Blob(["%PDF-1.4"], { type: "application/pdf" });
  const body = createDocumentUploadBody(Object.assign(blob, { name: "lesson.pdf" }));
  assert.equal(body.get("file")?.name, "lesson.pdf");
});

test("authenticated API helper lets the browser set multipart boundaries", () => {
  const form = new FormData(); form.append("file", new Blob(["pdf"]), "x.pdf");
  assert.equal(new Headers(requestHeaders({ body: form })).has("Content-Type"), false);
  assert.equal(new Headers(requestHeaders({ body: "{}" })).get("Content-Type"), "application/json");
});

test("multipart API request carries bearer auth and browser-managed boundary", async () => {
  const previousFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/documents");
    captured = options;
    return new Response(JSON.stringify({ id: "document-id" }), { status: 201, headers: { "Content-Type": "application/json" } });
  };
  try {
    const form = new FormData(); form.append("file", new Blob(["pdf"]), "lesson.pdf");
    const reply = await request("/documents", { method: "POST", headers: { Authorization: "Bearer test-token" }, body: form });
    assert.equal(reply.id, "document-id");
    const headers = new Headers(captured.headers);
    assert.equal(headers.get("Authorization"), "Bearer test-token");
    assert.equal(headers.has("Content-Type"), false);
  } finally { globalThis.fetch = previousFetch; }
});

test("application route and dashboard navigation expose Documents", async () => {
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");
  const dashboard = await readFile(new URL("../src/Dashboard.tsx", import.meta.url), "utf8");
  assert.ok(app.includes("/documents/:documentId"));
  assert.ok(app.includes("/documents"));
  assert.ok(dashboard.includes("to=\"/documents\""));
});
