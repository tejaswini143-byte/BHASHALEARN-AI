import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";
import { readFileSync } from "node:fs";

const startServers = process.env.BHASHALEARN_E2E_START_SERVERS === "1";
const mockApi = process.env.BHASHALEARN_E2E_MOCK_API === "1";
const externalFrontendUrl = process.env.BHASHALEARN_E2E_FRONTEND_URL;
const allowMutations = process.env.BHASHALEARN_E2E_ALLOW_MUTATIONS === "1";
const useFakeEmbeddingProvider = process.env.BHASHALEARN_E2E_FAKE_EMBEDDINGS === "1";
const databaseUrl = process.env.BHASHALEARN_E2E_DATABASE_URL;

function assertDisposableDatabase(value: string | undefined): asserts value is string {
  if (!value) throw new Error("E2E mutations require BHASHALEARN_E2E_DATABASE_URL; no database fallback is permitted.");
  let parsed: URL;
  try { parsed = new URL(value); } catch { throw new Error("BHASHALEARN_E2E_DATABASE_URL must be a valid PostgreSQL URL."); }
  const databaseName = decodeURIComponent(parsed.pathname.replace(/^\//, ""));
  if (!/^postgres(?:ql)?(?:\+[^:]+)?:$/.test(parsed.protocol) || !/(?:test|e2e|disposable)/i.test(databaseName) || /^bhashalearn$/i.test(databaseName)) {
    throw new Error("E2E mutations require a separate PostgreSQL database whose name includes test, e2e, or disposable; the development database is not accepted.");
  }
  const developmentUrl = process.env.BHASHALEARN_DATABASE_URL || readDevelopmentDatabaseUrl();
  if (developmentUrl && sameDatabase(value, developmentUrl)) {
    throw new Error("The E2E database matches the configured development database. A separate disposable database is required.");
  }
}

function readDevelopmentDatabaseUrl() {
  for (const path of [resolve("..", ".env"), resolve("..", "backend", ".env")]) {
    try {
      const envFile = readFileSync(path, "utf8");
      const line = envFile.split(/\r?\n/).find(entry => /^\s*BHASHALEARN_DATABASE_URL\s*=/.test(entry));
      const value = line?.slice(line.indexOf("=") + 1).trim().replace(/^(["'])(.*)\1$/, "$2");
      if (value) return value;
    } catch { /* Continue to the backend-local environment file without printing file content. */ }
  }
  return undefined;
}

function sameDatabase(left: string, right: string) {
  try {
    const a = new URL(left);
    const b = new URL(right);
    return a.hostname.toLowerCase() === b.hostname.toLowerCase()
      && (a.port || "5432") === (b.port || "5432")
      && decodeURIComponent(a.pathname).toLowerCase() === decodeURIComponent(b.pathname).toLowerCase();
  } catch { return false; }
}

if (allowMutations) assertDisposableDatabase(databaseUrl);
if (startServers && !mockApi) assertDisposableDatabase(databaseUrl);

const python = process.env.BHASHALEARN_E2E_PYTHON || (process.platform === "win32"
  ? resolve("..", ".venv", "Scripts", "python.exe")
  : resolve("..", ".venv", "bin", "python"));
const quote = (value: string) => `"${value.replaceAll('"', '\\"')}"`;
const testBackendPort = Number(process.env.BHASHALEARN_E2E_BACKEND_PORT || 8012);
const testFrontendPort = Number(process.env.BHASHALEARN_E2E_FRONTEND_PORT || (startServers ? 5184 : 5185));
const dedicatedBackendUrl = `http://127.0.0.1:${testBackendPort}`;
const dedicatedFrontendUrl = `http://127.0.0.1:${testFrontendPort}`;
const frontendUrl = externalFrontendUrl || dedicatedFrontendUrl;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 7_500 },
  reporter: [["list"], ["html", { outputFolder: process.env.BHASHALEARN_E2E_REPORT_DIR || "playwright-report-int13", open: "never" }]],
  outputDir: process.env.BHASHALEARN_E2E_ARTIFACT_DIR || "test-results-int13",
  use: {
    baseURL: startServers ? dedicatedFrontendUrl : frontendUrl,
    browserName: "chromium",
    headless: process.env.BHASHALEARN_E2E_HEADED !== "1",
    screenshot: "only-on-failure",
    trace: "on-first-retry",
    ...devices["Desktop Chrome"],
    launchOptions: process.env.BHASHALEARN_E2E_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.BHASHALEARN_E2E_CHROMIUM_EXECUTABLE }
      : undefined,
  },
  webServer: startServers ? [
    ...(!mockApi ? [{
      command: `${quote(python)} -m uvicorn ${useFakeEmbeddingProvider ? "backend.tests.adv02_e2e_server:app" : "backend.app.main:app"} --host 127.0.0.1 --port ${testBackendPort}`,
      cwd: "..",
      url: `${dedicatedBackendUrl}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        BHASHALEARN_DATABASE_URL: databaseUrl!,
        BHASHALEARN_JWT_SECRET_KEY: process.env.BHASHALEARN_E2E_JWT_SECRET || "e2e-only-secret-key-not-for-production",
        BHASHALEARN_DOCUMENT_STORAGE_DIR: resolve("..", "test-data", "private-documents"),
      },
    }] : []),
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${testFrontendPort} --strictPort`,
      cwd: ".",
      url: dedicatedFrontendUrl,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { BHASHALEARN_API_PROXY_TARGET: dedicatedBackendUrl },
    },
  ] : undefined,
});
