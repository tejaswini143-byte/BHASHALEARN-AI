import { Link } from "react-router-dom";
import "./session-modes.css";

type Mode = "chat" | "voice" | "visual" | "teacher";
type Props = { sessionId?: string | null; active: Mode };
const modes: Array<{ id: Mode; label: string; path: string }> = [
  { id: "chat", label: "Chat", path: "/classroom" },
  { id: "voice", label: "Voice", path: "/voice" },
  { id: "visual", label: "Visual", path: "/visual" },
  { id: "teacher", label: "Teacher", path: "/teacher" },
];

export function SessionModeNav({ sessionId, active }: Props) {
  return <nav className="session-mode-nav" aria-label="Learning modes">
    {modes.map(mode => {
      const to = sessionId ? `${mode.path}?session=${encodeURIComponent(sessionId)}` : mode.path;
      return <Link key={mode.id} to={to} className={active === mode.id ? "session-mode-active" : ""} aria-current={active === mode.id ? "page" : undefined}>
        {mode.label}
      </Link>;
    })}
  </nav>;
}
