import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import ts from "typescript";

const require = createRequire(import.meta.url);
require.extensions[".ts"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText, filename);
require.extensions[".tsx"] = (module, filename) => module._compile(ts.transpileModule(require("node:fs").readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
require.extensions[".css"] = () => {};
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../src");
const auth = require(resolve(root, "auth.ts"));
const api = require(resolve(root, "memoryApi.ts"));

function setSessionToken(token) {
  globalThis.sessionStorage = { getItem: key => key === "bhashalearn_access_token" ? token : null };
}

test("memory API lists and creates memories with the current bearer token", async () => {
  setSessionToken("student-session-token");
  const previousFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(url.endsWith("/memories") && options.method === "POST"
      ? { id: "m-1", topic: "Fractions", note: "Use pictures", created_at: "2026-01-01T00:00:00Z" }
      : [{ id: "m-1", topic: "Fractions", note: "Use pictures", created_at: "2026-01-01T00:00:00Z" }]), { status: url.endsWith("/memories") && options.method === "POST" ? 201 : 200 });
  };
  try {
    const created = await api.createMemory({ topic: "Fractions", note: "Use pictures" });
    const items = await api.listMemories();
    assert.equal(created.id, "m-1");
    assert.deepEqual(items.map(item => item.topic), ["Fractions"]);
    assert.equal(calls.length, 2);
    for (const call of calls) assert.equal(new Headers(call.options.headers).get("Authorization"), "Bearer student-session-token");
    assert.equal(JSON.parse(calls[0].options.body).note, "Use pictures");
  } finally { globalThis.fetch = previousFetch; }
});

test("memory API corrects and deletes only by memory resource ID", async () => {
  setSessionToken("student-session-token");
  const previousFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return options.method === "DELETE"
      ? new Response(null, { status: 204 })
      : new Response(JSON.stringify({ id: "private/id", topic: "Decimals", note: "Show a number line", created_at: "2026-01-01T00:00:00Z" }), { status: 200 });
  };
  try {
    const corrected = await api.updateMemory("private/id", { topic: "Decimals", note: "Show a number line" });
    await api.deleteMemory(corrected.id);
    assert.equal(corrected.note, "Show a number line");
    assert.equal(calls[0].url, "/api/v1/memories/private%2Fid");
    assert.equal(calls[0].options.method, "PATCH");
    assert.equal(calls[1].options.method, "DELETE");
    for (const call of calls) assert.equal(new Headers(call.options.headers).get("Authorization"), "Bearer student-session-token");
  } finally { globalThis.fetch = previousFetch; }
});

test("memory API rejects missing authentication without making a request", async () => {
  setSessionToken(null);
  const previousFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => { called = true; throw new Error("must not call fetch"); };
  try {
    assert.throws(() => api.listMemories(), error => error instanceof auth.ApiError && error.status === 401);
    assert.equal(called, false);
  } finally { globalThis.fetch = previousFetch; }
});

test("memory API surfaces backend validation and service errors", async () => {
  setSessionToken("student-session-token");
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Memory note is too long" }), { status: 422 });
  try {
    await assert.rejects(api.createMemory({ topic: "X", note: "bad" }), error => error instanceof auth.ApiError && error.status === 422 && error.message === "Memory note is too long");
  } finally { globalThis.fetch = previousFetch; }
});

test("memory screen exposes loading, empty, create, correct, confirm delete, and error UI", async () => {
  const source = await readFile(new URL("../src/Memories.tsx", import.meta.url), "utf8");
  for (const expected of ["Loading your learning memories", "No memories yet", "Add a memory", "Save correction", "Correct", "window.confirm", "Delete", "role=\"alert\"", "role=\"status\"", "createMemory", "updateMemory", "deleteMemory", "listMemories"]) assert.ok(source.includes(expected), `missing memory UI contract: ${expected}`);
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");
  const dashboard = await readFile(new URL("../src/Dashboard.tsx", import.meta.url), "utf8");
  assert.ok(app.includes('path="/memories"'));
  assert.ok(dashboard.includes('to="/memories"'));
});
