import { HoloSidebar } from "../HoloUI";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Student } from "../auth";
import { FeatureNavigation } from "./FeatureNavigation";

export function DashboardShell({ student, onSignOut, children }: { student: Student; onSignOut: () => void; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        menuButton.current?.focus();
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const closeMenu = () => setOpen(false);

  return <div className="cc-app">
    <HoloSidebar id="dashboard-sidebar" className={"cc-sidebar" + (open ? " open" : "")}>
      <Link to="/dashboard" className="cc-brand" onClick={closeMenu}>✦ BHASHA<strong>LEARN</strong> AI</Link>
      <nav id="dashboard-navigation" className="cc-nav" aria-label="Dashboard navigation">
        <a href="#overview" aria-current="page" onClick={closeMenu}>Overview</a>
        <a href="#timeline" onClick={closeMenu}>Learning timeline</a>
        <a href="#mastery" onClick={closeMenu}>Mastery</a>
        <a href="#features" onClick={closeMenu}>Learning tools</a>
        <Link to="/knowledge-studio" onClick={closeMenu}>Knowledge Studio</Link>
        <Link to="/memories" onClick={closeMenu}>Learning memories</Link>
      </nav>
      <FeatureNavigation compact onNavigate={closeMenu} />
      <div className="cc-profile"><strong>{student.display_name}</strong><small>{student.email}</small></div>
    </HoloSidebar>
    {open && <button type="button" className="cc-sidebar-backdrop" aria-label="Dismiss navigation overlay" onClick={() => { closeMenu(); menuButton.current?.focus(); }} />}
    <div className="cc-main">
      <header className="cc-topbar">
        <button ref={menuButton} type="button" className="cc-menu" aria-label={open ? "Close dashboard navigation" : "Open dashboard navigation"} aria-expanded={open} aria-controls="dashboard-sidebar" onClick={() => setOpen(value => !value)}>Menu</button>
        <span>Workspace / Command center</span>
        <button type="button" onClick={onSignOut}>Sign out</button>
      </header>
      <main id="overview" className="cc-content">{children}</main>
    </div>
  </div>;
}
