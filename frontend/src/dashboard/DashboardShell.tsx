import { HoloSidebar } from "../HoloUI";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import type { Student } from "../auth";

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
      <Link to="/dashboard" className="cc-brand" onClick={closeMenu}><span className="cc-brand-mark" aria-hidden="true">▣</span><span>BHASHA<strong>LEARN</strong><small>AI</small></span></Link>
      <nav id="dashboard-navigation" className="cc-nav" aria-label="Dashboard navigation">
        <NavLink to="/dashboard" end onClick={closeMenu}><span aria-hidden="true">⌂</span> Dashboard</NavLink>
        <NavLink to="/voice" onClick={closeMenu}><span aria-hidden="true">◉</span> AI Classroom</NavLink>
        <NavLink to="/chat" onClick={closeMenu}><span aria-hidden="true">▤</span> Chatbot</NavLink>
        <NavLink to="/documents" onClick={closeMenu}><span aria-hidden="true">▧</span> PDF Learning</NavLink>
        <NavLink to="/courses" onClick={closeMenu}><span aria-hidden="true">⌑</span> My Courses</NavLink>
        <NavLink to="/timeline" onClick={closeMenu}><span aria-hidden="true">◷</span> Timeline</NavLink>
        <NavLink to="/progress-analytics" onClick={closeMenu}><span aria-hidden="true">▥</span> Progress</NavLink>
      </nav>
      <nav className="cc-nav cc-nav-bottom" aria-label="Account navigation">
        <NavLink to="/settings" onClick={closeMenu}><span aria-hidden="true">⚙</span> Settings</NavLink>
        <button type="button" onClick={() => { closeMenu(); onSignOut(); }}><span aria-hidden="true">↪</span> Logout</button>
      </nav>
      <div className="cc-profile"><span className="cc-avatar" aria-hidden="true">{student.display_name.slice(0, 1).toUpperCase()}</span><div><strong>{student.display_name}</strong><small>Student</small></div></div>
    </HoloSidebar>
    {open && <button type="button" className="cc-sidebar-backdrop" aria-label="Dismiss navigation overlay" onClick={() => { closeMenu(); menuButton.current?.focus(); }} />}
    <div className="cc-main">
      <header className="cc-topbar">
        <button ref={menuButton} type="button" className="cc-menu" aria-label={open ? "Close dashboard navigation" : "Open dashboard navigation"} aria-expanded={open} aria-controls="dashboard-sidebar" onClick={() => setOpen(value => !value)}>Menu</button>
        <span><small>Workspace</small><b aria-hidden="true">/</b> Dashboard</span>
        <div className="cc-topbar-actions"><Link to="/settings" aria-label="Account settings">⚙</Link><span className="cc-top-avatar" aria-hidden="true">{student.display_name.slice(0, 1).toUpperCase()}</span></div>
      </header>
      <main id="overview" className="cc-content">{children}</main>
    </div>
    <nav className="cc-mobile-nav" aria-label="Mobile dashboard navigation">
      <NavLink to="/dashboard" end><span aria-hidden="true">⌂</span>Home</NavLink>
      <NavLink to="/voice"><span aria-hidden="true">◉</span>Classroom</NavLink>
      <NavLink to="/chat"><span aria-hidden="true">▤</span>Chat</NavLink>
      <NavLink to="/courses"><span aria-hidden="true">⌑</span>Courses</NavLink>
      <NavLink to="/progress-analytics"><span aria-hidden="true">▥</span>Progress</NavLink>
    </nav>
  </div>;
}
