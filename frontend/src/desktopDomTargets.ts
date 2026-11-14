export type DesktopTarget = {
  id: string;
  role: string;
  name: string;
  kind: "window" | "button" | "link" | "text" | "search" | "other";
};

export type ApprovedSite = { id: string; name: string; url: string };

const APPROVED_HOSTS = new Set(["127.0.0.1", "localhost"]);
const APPROVED_PORTS = new Set(["5173", "5184", "5185", "5198", "5199", "5200", "5201", "5202", "5203", "15199"]);
const APPROVED_PATHS = new Set(["/desktop-control-test.html", "/desktop-control-sandbox.html"]);

function qaWindow(): Window | null {
  try {
    const top = window.top;
    if (!top) return null;
    const url = new URL(top.location.href);
    if (url.protocol !== "http:" || !APPROVED_HOSTS.has(url.hostname) || !APPROVED_PORTS.has(url.port)) return null;
    if (!APPROVED_PATHS.has(url.pathname) || !top.document.title.includes("BHASHALEARN Desktop Control QA")) return null;
    return top;
  } catch {
    // Cross-origin documents are never inspected or controlled.
    return null;
  }
}

function labelFor(element: HTMLElement): string {
  const explicit = element.getAttribute("aria-label")?.trim();
  if (explicit) return explicit.slice(0, 120);
  const labels = (element as HTMLInputElement).labels;
  const fromLabel = labels ? Array.from(labels).map(label => label.innerText.trim()).join(" ").trim() : "";
  if (fromLabel) return fromLabel.slice(0, 120);
  const text = element.innerText?.replace(/\s+/g, " ").trim();
  if (text) return text.slice(0, 120);
  // Placeholders and values are intentionally excluded; they may contain private text.
  return "";
}

function allowedDocuments(top: Window): Array<{ doc: Document; frame?: HTMLIFrameElement }> {
  const docs: Array<{ doc: Document; frame?: HTMLIFrameElement }> = [{ doc: top.document }];
  const frame = top.document.querySelector<HTMLIFrameElement>("#approved-site-frame");
  try {
    const child = frame?.contentWindow;
    if (frame && child) {
      const url = new URL(child.location.href);
      if (url.origin === top.location.origin && url.pathname === "/desktop-control-sandbox.html") docs.push({ doc: child.document, frame });
    }
  } catch { /* Never inspect cross-origin frames. */ }
  return docs;
}

export function getDesktopQaContext(): { targets: DesktopTarget[]; approved_sites: Record<string, string> } | null {
  const top = qaWindow();
  if (!top) return null;
  const targets: DesktopTarget[] = [];
  for (const { doc, frame } of allowedDocuments(top)) {
    for (const element of Array.from(doc.querySelectorAll<HTMLElement>("[data-desktop-target]"))) {
      if (!element.isConnected || element.hasAttribute("disabled") || element.getAttribute("aria-disabled") === "true") continue;
      const id = `${frame ? "sandbox-" : ""}${element.dataset.desktopTarget?.trim() || ""}`;
      const name = labelFor(element);
      if (!id || !name) continue;
      const kind = element.dataset.desktopKind;
      const acceptedKind: DesktopTarget["kind"] = kind === "button" || kind === "link" || kind === "text" || kind === "search" ? kind : "other";
      targets.push({ id, role: element.getAttribute("role") || element.tagName.toLowerCase(), name, kind: acceptedKind });
    }
  }
  const origin = top.location.origin;
  return {
    targets: targets.slice(0, 40),
    approved_sites: {
      qa_home: `${origin}/desktop-control-test.html`,
      qa_sandbox: `${origin}/desktop-control-sandbox.html`,
    },
  };
}

export function getDesktopTargetScreenPoint(id: string): { x: number; y: number } | null {
  const top = qaWindow();
  if (!top || !/^[a-zA-Z0-9_-]{1,64}$/.test(id)) return null;
  const found = findTarget(top, id);
  const element = found?.element;
  if (!element || element.hasAttribute("disabled") || element.getAttribute("aria-disabled") === "true") return null;
  element.scrollIntoView({ block: "center", inline: "center", behavior: "instant" as ScrollBehavior });
  const ownRect = element.getBoundingClientRect();
  const frameRect = found.frame?.getBoundingClientRect();
  if (found.frame && (ownRect.top < 0 || ownRect.left < 0 || ownRect.bottom > found.frame.clientHeight || ownRect.right > found.frame.clientWidth)) return null;
  const rect = {
    left: ownRect.left + (frameRect?.left || 0), top: ownRect.top + (frameRect?.top || 0),
    right: ownRect.right + (frameRect?.left || 0), bottom: ownRect.bottom + (frameRect?.top || 0),
    width: ownRect.width, height: ownRect.height,
  };
  if (rect.width <= 0 || rect.height <= 0 || rect.top < 0 || rect.left < 0 || rect.bottom > top.innerHeight || rect.right > top.innerWidth) return null;
  const scale = top.devicePixelRatio || 1;
  const chromeTop = Math.max(0, top.outerHeight - top.innerHeight);
  return {
    x: Math.round((top.screenX + rect.left + rect.width / 2) * scale),
    y: Math.round((top.screenY + chromeTop + rect.top + rect.height / 2) * scale),
  };
}

export function resolveDesktopTarget(id: string): HTMLElement | null {
  const top = qaWindow();
  if (!top || !/^[a-zA-Z0-9_-]{1,64}$/.test(id)) return null;
  const target = findTarget(top, id)?.element;
  return target?.isConnected ? target : null;
}

export function isApprovedQaTextFieldFocused(): boolean {
  const top = qaWindow();
  const focused = top?.document.activeElement;
  const element = focused as HTMLElement | null;
  return Boolean(element && ["INPUT", "TEXTAREA"].includes(element.tagName)
    && element.hasAttribute("data-desktop-target")
    && element.closest("[aria-label='Approved desktop test controls'], main") !== null);
}

function findTarget(top: Window, id: string): { element: HTMLElement; frame?: HTMLIFrameElement } | null {
  const sandbox = id.startsWith("sandbox-");
  const sourceId = sandbox ? id.slice("sandbox-".length) : id;
  for (const entry of allowedDocuments(top)) {
    if (Boolean(entry.frame) !== sandbox) continue;
    const element = entry.doc.querySelector<HTMLElement>(`[data-desktop-target="${CSS.escape(sourceId)}"]`);
    if (element) return { element, frame: entry.frame };
  }
  return null;
}

export function openApprovedDesktopSite(siteId: string): boolean {
  const context = getDesktopQaContext();
  if (!context) return false;
  const url = context.approved_sites[siteId];
  if (!url) return false;
  const destination = new URL(url);
  const current = qaWindow();
  if (!current || destination.origin !== current.location.origin || !APPROVED_PATHS.has(destination.pathname)) return false;
  const frame = current.document.querySelector<HTMLIFrameElement>("#approved-site-frame");
  if (!frame) return false;
  // Keep the voice panel alive and show the approved local test site inside its isolated frame.
  frame.src = destination.href;
  return true;
}

export function scrollApprovedPage(direction: "up" | "down"): boolean {
  const top = qaWindow();
  if (!top) return false;
  const frame = top.document.querySelector<HTMLIFrameElement>("#approved-site-frame");
  const activePage = frame?.contentWindow && frame.contentWindow.location.origin === top.location.origin ? frame.contentWindow : top;
  activePage.scrollBy({ top: direction === "down" ? Math.max(240, activePage.innerHeight * 0.65) : -Math.max(240, activePage.innerHeight * 0.65), behavior: "smooth" });
  return true;
}

export function navigateApprovedPage(direction: "back" | "forward"): boolean {
  const top = qaWindow();
  const frame = top?.document.querySelector<HTMLIFrameElement>("#approved-site-frame");
  if (!top || !frame?.contentWindow) return false;
  try {
    const child = frame.contentWindow;
    const url = new URL(child.location.href);
    if (url.origin !== top.location.origin || url.pathname !== "/desktop-control-sandbox.html") return false;
    child.history[direction]();
    return true;
  } catch { return false; }
}
