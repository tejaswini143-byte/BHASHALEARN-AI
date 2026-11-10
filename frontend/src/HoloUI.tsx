import type { AnchorHTMLAttributes, ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

type Classed<T> = T & { className?: string };

export function HoloCard({ className = "", ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={`holo-card ${className}`.trim()} {...props} />;
}

export function HoloPanel({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`holo-panel ${className}`.trim()} {...props} />;
}

export function HoloHeader({ className = "", ...props }: HTMLAttributes<HTMLElement>) {
  return <header className={`holo-header ${className}`.trim()} {...props} />;
}

export function HoloSidebar({ className = "", ...props }: HTMLAttributes<HTMLElement>) {
  return <aside className={`holo-sidebar ${className}`.trim()} {...props} />;
}

type HoloButtonProps =
  | ({ as?: "button" } & ButtonHTMLAttributes<HTMLButtonElement>)
  | ({ as: "a" } & AnchorHTMLAttributes<HTMLAnchorElement>);

export function HoloButton(props: HoloButtonProps) {
  const { className = "", ...rest } = props;
  if (props.as === "a") return <a className={`holo-button ${className}`.trim()} {...rest as AnchorHTMLAttributes<HTMLAnchorElement>} />;
  return <button className={`holo-button ${className}`.trim()} {...rest as ButtonHTMLAttributes<HTMLButtonElement>} />;
}

export function StatusIndicator({ label, status = "ready" }: { label: string; status?: "ready" | "busy" | "idle" | "error" }) {
  return <span className={`holo-status holo-status-${status}`}><span aria-hidden="true" />{label}</span>;
}

export function LoadingSkeleton({ label = "Loading", lines = 2 }: { label?: string; lines?: number }) {
  return <div className="holo-skeleton" role="status" aria-label={label}><span className="holo-skeleton-title"/>{Array.from({ length: lines }, (_, i) => <span key={i} className="holo-skeleton-line"/>)}<span className="sr-only">{label}…</span></div>;
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="holo-state holo-empty"><span className="holo-state-mark" aria-hidden="true">◇</span><h2>{title}</h2>{children && <p>{children}</p>}{action}</div>;
}

export function ErrorState({ title = "Something went wrong", children, action }: { title?: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="holo-state holo-error" role="alert"><span className="holo-state-mark" aria-hidden="true">!</span><h2>{title}</h2>{children && <p>{children}</p>}{action}</div>;
}

export function HoloAction({ className = "", ...props }: Classed<ButtonHTMLAttributes<HTMLButtonElement>>) {
  return <HoloButton className={className} {...props} />;
}
