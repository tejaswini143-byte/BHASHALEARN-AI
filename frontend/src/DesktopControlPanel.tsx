import { useEffect, useRef, useState } from "react";
import { getToken } from "./auth";
import { createDesktopExecutionGate } from "./desktopExecution.mjs";
import {
  getDesktopQaContext, getDesktopTargetScreenPoint, isApprovedQaTextFieldFocused, navigateApprovedPage,
  openApprovedDesktopSite, resolveDesktopTarget,
} from "./desktopDomTargets";

type Action = {
  action: string;
  text?: string | null;
  target_id?: string | null;
  site_id?: string | null;
  app_id?: string | null;
  url?: string | null;
  shortcut?: string | null;
  target_name?: string | null;
  steps?: Action[] | null;
  clarification?: string | null;
};

type DesktopSnapshot = {
  snapshot_id: string;
  active_window_id: string | null;
  focused_target_id: string | null;
  active_app: string | null;
  targets: Array<{ id: string; role: string; name: string; kind: "window" | "button" | "link" | "text" | "search" | "other" }>;
};

function targetsForCommand(snapshot: DesktopSnapshot, transcript: string) {
  const text = transcript.toLocaleLowerCase();
  const namesField = /\b(search|message|address|url|text|input)\s*(bar|field|box)|\b(field|box|bar)\b/.test(text);
  if (/\b(open|search|type|write|enter|shortcut|copy|select all)\b/.test(text)
      && !/\b(click|move|focus|switch|close|minimize|maximize|scroll)\b/.test(text)
      && !namesField) return [];
  if (/\b(close|switch|minimize|maximize)\b/.test(text) && /\b(window|notepad|chrome|edge|browser)\b/.test(text)) {
    return snapshot.targets.filter(target => target.kind === "window");
  }
  if (/\b(scroll)\b/.test(text)) {
    return snapshot.targets.filter(target => target.kind === "window" && target.id === snapshot.active_window_id);
  }
  if (/\b(first|second|1st|2nd)\s+(link|result)\b/.test(text)) {
    return snapshot.targets.filter(target => target.kind === "link")
      .map((target, index) => ({ ...target, name: `Link ${index + 1}` }));
  }
  const ignored = new Set(["click", "move", "cursor", "mouse", "focus", "find", "the", "a", "an", "to", "on", "in", "into", "this", "that", "button", "link", "box", "field", "bar", "first", "second"]);
  const words = text.match(/[\p{L}\p{N}]+/gu)?.filter(word => word.length > 2 && !ignored.has(word)) || [];
  return snapshot.targets.filter(target => target.kind !== "window"
    && words.some(word => target.name.toLocaleLowerCase().includes(word)));
}

function bindNamedClickTargets(action: Action, transcript: string, targets: Array<{ id: string; name: string; kind: string }>): Action {
  if (action.action === "sequence") {
    const steps = (action.steps || []).map(step => bindNamedClickTargets(step, transcript, targets));
    const clarification = steps.find(step => step.action === "clarify");
    return clarification || { ...action, steps };
  }
  if (action.action !== "click" && action.action !== "click_target") return action;

  const normalized = transcript.normalize("NFC").toLocaleLowerCase();
  const requested = targets.filter(target => ["button", "link"].includes(target.kind)
    && normalized.includes(target.name.normalize("NFC").toLocaleLowerCase()));
  const names = [...new Set(requested.map(target => target.name.normalize("NFC").toLocaleLowerCase()))];
  if (names.length > 1) return { action: "clarify", clarification: "Which visible button or link do you mean?" };
  if (!requested.length && action.action === "click_target") {
    const ordinal = normalized.match(/\b(first|second|1st|2nd)\s+(link|result|button)\b/);
    if (ordinal) {
      const kind = ordinal[2] === "link" || ordinal[2] === "result" ? "link" : "button";
      const matchesByOrder = targets.filter(target => target.kind === kind);
      const index = ordinal[1] === "first" || ordinal[1] === "1st" ? 0 : 1;
      if (matchesByOrder[index]?.id === action.target_id) return action;
    }
    return { action: "clarify", clarification: "Please name a visible button or link. I blocked the unbound click." };
  }
  if (!requested.length) return { action: "clarify", clarification: "Please name a visible button or link. I blocked the unbound click." };
  const matches = requested.filter(target => target.name.normalize("NFC").toLocaleLowerCase() === names[0]);
  if (matches.length > 1) return { action: "clarify", clarification: `I found ${matches.length} targets named ${matches[0].name}. Which one do you mean?` };
  if (action.action === "click_target" && action.target_id !== matches[0].id) {
    return { action: "clarify", clarification: "Gemini selected a different element than the one you named. I blocked the click." };
  }
  return { action: "click_target", target_id: matches[0].id };
}

const requestedBase = import.meta.env.VITE_DESKTOP_COMPANION_URL;
const allowedCompanionBases = new Set(["http://127.0.0.1:18765", "http://127.0.0.1:18766", "http://127.0.0.1:18770"]);
const base = requestedBase && allowedCompanionBases.has(requestedBase) ? requestedBase : "http://127.0.0.1:18765";
const STOP_WORDS = /^(stop|emergency stop|desktop control stop|ఆపు|ఆపండి|అత్యవసరంగా ఆపు)$/iu;
const wait = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms));

export function DesktopControlPanel({ transcript, language = "mixed" }: { transcript: string; language?: "english" | "telugu" | "mixed" }) {
  const [pairing, setPairing] = useState("");
  const [connected, setConnected] = useState(false);
  const [active, setActive] = useState(false);
  const [status, setStatus] = useState("Disconnected");
  const [action, setAction] = useState<Action | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [reviewedTranscript, setReviewedTranscript] = useState("");
  const [closeConfirmed, setCloseConfirmed] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const executionGateRef = useRef(createDesktopExecutionGate());
  const activeRef = useRef(false);
  const nextPlanIdRef = useRef(0);
  const currentPlanRef = useRef<{ id: string; transcript: string; action: Action } | null>(null);
  const executionInProgressRef = useRef(false);
  const desktopSnapshotRef = useRef<DesktopSnapshot | null>(null);
  const languageCode = language === "english" ? "en" : language === "telugu" ? "te" : "mixed";

  useEffect(() => () => executionGateRef.current.disable(), []);

  useEffect(() => {
    executionGateRef.current.invalidatePlan();
    currentPlanRef.current = null;
    setReviewedTranscript("");
    setAction(null);
    setCloseConfirmed(false);
  }, [transcript]);

  async function companion(path: string, body?: object, authToken = pairing) {
    const response = await fetch(base + path, { method: path === "/health" || path === "/desktop/snapshot" ? "GET" : "POST", headers: { Authorization: `Bearer ${authToken}`, ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(value.error || `Companion returned ${response.status}`);
    return value;
  }

  async function speak(text: string) {
    const token = getToken(); if (!token) return;
    try {
      const response = await fetch("/api/v1/assistant/voice/speech", { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify({ text, language: languageCode }) });
      if (!response.ok || !response.headers.get("content-type")?.toLowerCase().startsWith("audio/wav")) return;
      const url = URL.createObjectURL(await response.blob());
      if (audioRef.current) { audioRef.current.src = url; await audioRef.current.play().catch(() => setStatus("Timbre audio is ready; press Play to hear it.")); }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch { /* Keep the recognized action visible if speech is unavailable. */ }
  }

  async function connect() {
    setBusy(true);
    try {
      const pairingResponse = await fetch(base + "/pair", { mode: "cors", cache: "no-store" });
      const pairingState = await pairingResponse.json().catch(() => ({}));
      if (!pairingResponse.ok || typeof pairingState.token !== "string") throw new Error(pairingState.error || "Open the local companion before connecting.");
      const localToken = pairingState.token as string;
      setPairing(localToken);
      const state = await companion("/health", undefined, localToken);
      const enabled = Boolean(state.active);
      activeRef.current = enabled;
      if (enabled) executionGateRef.current.enable(); else executionGateRef.current.disable();
      setConnected(true); setActive(enabled); setStatus(enabled ? "Connected · desktop control enabled" : "Connected · control disabled");
    } catch (error) { setConnected(false); setActive(false); setStatus(error instanceof Error ? error.message : "Connection failed"); }
    finally { setBusy(false); }
  }

  async function toggle() {
    setBusy(true);
    if (activeRef.current) {
      activeRef.current = false;
      executionGateRef.current.disable();
      currentPlanRef.current = null;
      setActive(false);
    }
    try {
      const state = await companion(active ? "/disable" : "/activate");
      const enabled = Boolean(state.active);
      activeRef.current = enabled;
      if (enabled) executionGateRef.current.enable(); else executionGateRef.current.disable();
      setActive(enabled); setStatus(enabled ? "Windows desktop control enabled" : "Desktop control disabled");
      if (state.active) void speak("Windows desktop control is enabled. Review every proposed action before execution.");
    } catch (error) { setStatus(error instanceof Error ? error.message : "Control request failed"); }
    finally { setBusy(false); }
  }

  async function interpret() {
    const normalized = transcript.normalize("NFC").trim();
    if (STOP_WORDS.test(normalized)) { await stop(); return; }
    if (!normalized || reviewedTranscript !== normalized) {
      setStatus("Review and confirm the Prisma transcript before asking Gemini to plan an action.");
      return;
    }
    const qaContext = getDesktopQaContext();
    const token = getToken(); if (!token) { setStatus("Sign in again to interpret a command."); return; }
    executionGateRef.current.invalidatePlan();
    currentPlanRef.current = null;
    setBusy(true); setAction(null);
    const requestEpoch = executionGateRef.current.snapshot();
    try {
      let targets = qaContext?.targets || [];
      let approved_sites = qaContext?.approved_sites || {};
      if (!qaContext) {
        const snapshot = await companion("/desktop/snapshot") as DesktopSnapshot;
        desktopSnapshotRef.current = snapshot;
        targets = targetsForCommand(snapshot, normalized);
        approved_sites = {};
      }
      const response = await fetch("/api/v1/assistant/desktop/interpret", {
        method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: normalized, targets, approved_sites }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.detail || "Gemini could not interpret this command");
      if (!activeRef.current || !executionGateRef.current.isCurrent(requestEpoch)) {
        setStatus("Emergency Stop cancelled the pending command.");
        return;
      }
      const proposed = bindNamedClickTargets(value.action as Action, normalized, targets);
      setCloseConfirmed(false);
      setAction(proposed);
      if (proposed.action === "clarify") {
        setStatus(proposed.clarification || "Please clarify which target you mean.");
        void speak(proposed.clarification || "Please clarify which target you mean.");
      } else {
        const planId = `${++nextPlanIdRef.current}:${Date.now()}`;
        executionGateRef.current.registerPlan(planId);
        currentPlanRef.current = { id: planId, transcript: normalized, action: proposed };
        setStatus("Review the proposed action before confirming.");
        void speak(`I understood ${describe(proposed)}. Confirm on screen to execute.`);
      }
    } catch (error) { setStatus(error instanceof Error ? error.message : "Interpretation failed"); }
    finally { setBusy(false); }
  }

  function describe(step: Action): string {
    if (step.action === "sequence") return (step.steps || []).map(describe).join(", then ");
    if (["click_target", "focus_target", "type_into", "search", "move_to_target", "switch_window", "minimize_window", "maximize_window", "close_window"].includes(step.action)) {
      const target = (desktopSnapshotRef.current?.targets || getDesktopQaContext()?.targets || []).find(item => item.id === step.target_id);
      return `${step.action.replaceAll("_", " ")} ${target?.name || "the selected target"}`;
    }
    if (step.action === "open_approved_site") return `open ${step.site_id === "qa_sandbox" ? "the QA sandbox" : "the desktop-control QA page"}`;
    if (step.action === "open_app") return `open ${step.app_id || "the selected app"}`;
    if (step.action === "open_website") return `open ${step.url || "the selected website"}`;
    if (step.action === "search_web" || step.action === "search_youtube") return `search ${step.action === "search_youtube" ? "YouTube" : "Google"} for “${step.text || "…"}”`;
    if (["click_visible", "focus_visible", "type_into_visible"].includes(step.action)) return `${step.action.replaceAll("_", " ")} ${step.target_name || "the named visible control"}`;
    if (step.action === "keyboard_shortcut") return `press ${step.shortcut || "the selected shortcut"}`;
    return step.action.replaceAll("_", " ");
  }

  function hasCloseAction(step: Action): boolean {
    return step.action === "close_window" || (step.action === "sequence" && (step.steps || []).some(hasCloseAction));
  }

  function requiresBoundTargets(step: Action): boolean {
    if (step.action === "sequence") return (step.steps || []).some(requiresBoundTargets);
    return !["open_app", "open_website", "search_web", "search_youtube", "open_approved_site", "navigate_back", "navigate_forward", "stop", "clarify"].includes(step.action);
  }

  function addWindowContext(step: Action, snapshot: DesktopSnapshot): Action {
    if (step.action === "sequence") return { ...step, steps: (step.steps || []).map(item => addWindowContext(item, snapshot)) };
    if (["scroll_up", "scroll_down"].includes(step.action) && !step.target_id) {
      return { ...step, target_id: snapshot.active_window_id };
    }
    return step;
  }

  function assertExecutionActive(executionEpoch: number) {
    executionGateRef.current.assertCurrent(executionEpoch);
  }

  async function executeStep(step: Action, executionEpoch: number): Promise<string> {
    assertExecutionActive(executionEpoch);
    if (step.action === "sequence") {
      const steps = step.steps || [];
      if (!steps.length || steps.length > 5) throw new Error("Only one to five sequential actions are supported.");
      const results: string[] = [];
      for (const item of steps) {
        assertExecutionActive(executionEpoch);
        results.push(await executeStep(item, executionEpoch));
        assertExecutionActive(executionEpoch);
        await wait(280);
      }
      return results.join("; ");
    }
    if (step.action === "clarify") throw new Error("Answer the clarification before confirming an action.");
    if (step.action === "stop") { await stop(); return "Emergency stop"; }
    if (step.action === "open_approved_site") {
      if (!openApprovedDesktopSite(step.site_id || "")) throw new Error("That website is outside the local QA allowlist.");
      return `opened ${step.site_id === "qa_sandbox" ? "QA sandbox" : "QA home"}`;
    }
    if (step.action === "navigate_back" || step.action === "navigate_forward") {
      if (!navigateApprovedPage(step.action === "navigate_back" ? "back" : "forward")) throw new Error("Browser history is available only inside the approved QA sandbox.");
      return step.action === "navigate_back" ? "went back in the QA sandbox" : "went forward in the QA sandbox";
    }
    if (step.action === "scroll_up" || step.action === "scroll_down") {
      const page = window.top;
      const before = page?.scrollY ?? 0;
      if (!page || !getDesktopQaContext()) throw new Error("Scrolling is restricted to the approved local QA page.");
      page.scrollBy({ top: step.action === "scroll_down" ? 500 : -500, behavior: "instant" });
      await wait(180);
      assertExecutionActive(executionEpoch);
      const after = page?.scrollY ?? before;
      if (after === before) throw new Error(`The approved page did not scroll (position stayed at ${before}px).`);
      return `${step.action === "scroll_down" ? "scrolled down" : "scrolled up"} (${before}→${after}px)`;
    }
    if (step.action === "click_target" || step.action === "focus_target" || step.action === "type_into" || step.action === "search") {
      const element = step.target_id ? resolveDesktopTarget(step.target_id) : null;
      const point = step.target_id ? getDesktopTargetScreenPoint(step.target_id) : null;
      if (!element || !point) throw new Error("That target is no longer visible in the approved QA page.");
      const name = getDesktopQaContext()?.targets.find(item => item.id === step.target_id)?.name || "target";
      await companion("/action", { action: "move_to", ...point });
      assertExecutionActive(executionEpoch);
      await wait(280); // The companion intentionally rate-limits physical actions to at most four per second.
      assertExecutionActive(executionEpoch);
      if (step.action === "focus_target") { element.focus(); return `focused ${name}`; }
      if (step.action === "click_target") {
        const context = getDesktopQaContext();
        const page = window.top;
        if (element.tagName === "A") {
          const destination = (element as HTMLAnchorElement).href;
          if (!context || !page || !Object.values(context.approved_sites).includes(destination)) {
            throw new Error("That link is outside the approved local QA destinations.");
          }
          element.click();
          await wait(250);
          if (page.location.href !== destination) throw new Error("The approved link did not navigate to its exact destination.");
          return `navigated to ${destination}`;
        }
        element.click();
        await wait(30);
        return `clicked ${name} by its uniquely resolved QA target`;
      }
      if (!(element.tagName === "INPUT" || element.tagName === "TEXTAREA") || !step.text) throw new Error("The selected target is not a supported local text field.");
      element.focus();
      const control = element as HTMLInputElement | HTMLTextAreaElement;
      const ownerWindow = element.ownerDocument.defaultView;
      if (!ownerWindow || element.ownerDocument.activeElement !== element) throw new Error(`Could not focus ${name}.`);
      const valueDescriptor = Object.getOwnPropertyDescriptor(
        element.tagName === "INPUT" ? ownerWindow.HTMLInputElement.prototype : ownerWindow.HTMLTextAreaElement.prototype,
        "value",
      );
      if (!valueDescriptor?.set) throw new Error(`Could not enter text into ${name}.`);
      const start = control.selectionStart ?? control.value.length;
      const end = control.selectionEnd ?? control.value.length;
      valueDescriptor.set.call(control, `${control.value.slice(0, start)}${step.text}${control.value.slice(end)}`);
      control.setSelectionRange(start + step.text.length, start + step.text.length);
      control.dispatchEvent(new ownerWindow.Event("input", { bubbles: true, composed: true }));
      control.dispatchEvent(new ownerWindow.Event("change", { bubbles: true }));
      await wait(30);
      const fieldValue = control.value;
      if (!["INPUT", "TEXTAREA"].includes(element.tagName) || !fieldValue.includes(step.text)) {
        throw new Error(`Text entry failed: ${name} did not contain the dictated text afterward.`);
      }
      if (step.action === "search") { await wait(280); await companion("/action", { action: "enter" }); return `searched for the dictated phrase in ${name}`; }
      return `entered dictated text into ${name}`;
    }
    if (["center", "left", "right", "up", "down", "click", "double_click", "type", "enter"].includes(step.action)) {
      if ((step.action === "type" || step.action === "enter") && !isApprovedQaTextFieldFocused()) throw new Error("Focus an approved QA text field before typing or pressing Enter.");
      await companion("/action", { action: step.action, ...(step.text ? { text: step.text } : {}) });
      return step.action === "type" ? "typed the approved dictated text" : step.action.replaceAll("_", " ");
    }
    throw new Error("That desktop action is not supported.");
  }

  async function execute(planId?: string) {
    if (!active || !action || action.action === "clarify") return;
    const normalized = transcript.normalize("NFC").trim();
    const plan = currentPlanRef.current;
    if (!planId || !plan || plan.id !== planId || plan.action !== action || plan.transcript !== normalized) {
      executionGateRef.current.invalidatePlan();
      currentPlanRef.current = null;
      setAction(null);
      setStatus("The transcript changed. Review it again before planning another action.");
      return;
    }
    if (reviewedTranscript !== normalized) {
      executionGateRef.current.invalidatePlan();
      currentPlanRef.current = null;
      setAction(null);
      setStatus("The transcript changed. Review it again before planning another action.");
      return;
    }
    const currentContext = getDesktopQaContext();
    if (hasCloseAction(action) && !closeConfirmed) { setStatus("Confirm that closing this window may discard unsaved work."); return; }
    if (executionInProgressRef.current) return;
    executionInProgressRef.current = true;
    let executionEpoch: number;
    try { executionEpoch = executionGateRef.current.begin(planId); }
    catch (error) {
      executionInProgressRef.current = false;
      setStatus(error instanceof Error ? error.message : "A fresh confirmation is required.");
      return;
    }
    const approvedAction = action;
    currentPlanRef.current = null;
    setAction(null);
    setBusy(true);
    try {
      let summary: string;
      if (currentContext) {
        summary = await executeStep(approvedAction, executionEpoch);
      } else {
        const snapshot = desktopSnapshotRef.current;
        if (!snapshot) throw new Error("Refresh Windows UI Automation targets before executing this action.");
        const currentSnapshot = await companion("/desktop/snapshot") as DesktopSnapshot;
        const needsBoundTargets = requiresBoundTargets(approvedAction);
        if (needsBoundTargets && (currentSnapshot.active_window_id !== snapshot.active_window_id
          || currentSnapshot.focused_target_id !== snapshot.focused_target_id
          || JSON.stringify(currentSnapshot.targets) !== JSON.stringify(snapshot.targets))) {
          throw new Error("The active window or its UI Automation targets changed after planning. Reinterpret the command.");
        }
        assertExecutionActive(executionEpoch);
        const executionPayload = {
          snapshot_id: needsBoundTargets ? snapshot.snapshot_id : currentSnapshot.snapshot_id,
          active_window_id: needsBoundTargets ? snapshot.active_window_id : currentSnapshot.active_window_id,
          focus_target_id: needsBoundTargets ? snapshot.focused_target_id : currentSnapshot.focused_target_id,
          confirmed_close: closeConfirmed,
          action: addWindowContext(approvedAction, snapshot),
        };
        const confirmation = await companion("/desktop/confirm", executionPayload) as { confirmation_token?: string };
        if (!confirmation.confirmation_token) throw new Error("The companion did not issue a one-time action confirmation.");
        assertExecutionActive(executionEpoch);
        const response = await companion("/desktop/execute", { ...executionPayload, confirmation_token: confirmation.confirmation_token });
        assertExecutionActive(executionEpoch);
        summary = response.action === "sequence" ? `completed ${response.steps?.length || 0} approved desktop steps` : `completed ${response.action || approvedAction.action}`;
      }
      // An in-flight request may finish after Emergency Stop or a changed transcript.
      // Never display a stale success as a newly approved execution.
      assertExecutionActive(executionEpoch);
      setHistory(items => [summary, ...items].slice(0, 20)); setStatus(`Completed: ${summary}`); setAction(null); void speak(`Completed. ${summary}.`);
    } catch (error) {
      if (!activeRef.current || !executionGateRef.current.isCurrent(executionEpoch)) setStatus("Stopped: Emergency Stop cancelled the remaining workflow.");
      else setStatus(error instanceof Error ? error.message : "Action failed");
    }
    finally { executionGateRef.current.finish(executionEpoch); executionInProgressRef.current = false; setBusy(false); }
  }

  async function stop() {
    executionGateRef.current.disable();
    activeRef.current = false;
    currentPlanRef.current = null;
    setActive(false); setAction(null); setReviewedTranscript("");
    try { await companion("/stop"); setStatus("Emergency stop sent; explicitly re-enable to continue."); }
    catch { setConnected(false); setStatus("Stop could not reach the companion. Use its PyAutoGUI fail-safe or close its process."); }
  }

  const clarification = action?.action === "clarify";
  return <section aria-label="Windows desktop control" style={{ margin: "12px 0", padding: 14, border: "1px solid #53648d", borderRadius: 12, background: "#101a30" }}>
    <strong>Opt-in Windows desktop control</strong> <span role="status">· {status}</span>
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
      <button type="button" disabled={busy} onClick={() => void connect()}>Connect to local companion</button>
      <button type="button" disabled={!connected || busy} onClick={() => void toggle()}>{active ? "Disable control" : "Enable control"}</button>
      <button type="button" onClick={() => void stop()}>Emergency Stop</button>
    </div>
    <p>Prisma transcript: {transcript || "Record a command first."}</p>
    {transcript.trim() && !STOP_WORDS.test(transcript.normalize("NFC").trim()) && <button type="button" disabled={!connected || !active || busy || reviewedTranscript === transcript.normalize("NFC").trim()} onClick={() => { executionGateRef.current.invalidatePlan(); currentPlanRef.current = null; setReviewedTranscript(transcript.normalize("NFC").trim()); setAction(null); setStatus("Transcript reviewed. You may ask Gemini to prepare a plan."); }}>I reviewed this transcript</button>}
    <button type="button" disabled={!connected || !active || !transcript.trim() || busy || (!STOP_WORDS.test(transcript.normalize("NFC").trim()) && reviewedTranscript !== transcript.normalize("NFC").trim())} onClick={() => void interpret()}>{STOP_WORDS.test(transcript.normalize("NFC").trim()) ? "Voice Emergency Stop" : "Interpret with Gemini"}</button>
    {action && (clarification
      ? <div role="status" aria-label="Clarification needed"><p>{action.clarification}</p><button type="button" onClick={() => setAction(null)}>Clear clarification</button></div>
      : <div role="group" aria-label="Confirm desktop action"><p>Proposed: <b>{describe(action)}</b>{action.action === "sequence" && <ol>{(action.steps || []).map((step, index) => <li key={index}>{describe(step)}</li>)}</ol>}</p>
        {hasCloseAction(action) && <label><input type="checkbox" checked={closeConfirmed} disabled={!active || busy} onChange={event => setCloseConfirmed(event.target.checked)}/> I confirm closing this window may discard unsaved work.</label>}
        <button type="button" disabled={!active || busy || (hasCloseAction(action) && !closeConfirmed)} onClick={() => void execute(currentPlanRef.current?.id)}>Confirm and execute</button><button type="button" onClick={() => { executionGateRef.current.invalidatePlan(); currentPlanRef.current = null; setCloseConfirmed(false); setAction(null); }}>Cancel</button></div>)}
    <button type="button" onClick={() => setHistory([])}>Clear action history</button><ol aria-label="Recent desktop actions">{history.map((item,index)=><li key={`${index}-${item}`}>{item}</li>)}</ol>
    <audio ref={audioRef} controls aria-label="Gnani Timbre action confirmation" />
  </section>;
}
