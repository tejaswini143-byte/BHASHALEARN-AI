import { useState } from "react";
import { deleteFutureSeekerReflection, listFutureSeekerReflections, type SavedFutureSeekerReflection } from "./futureSeekerApi";
import { getToken } from "./auth";

export function FutureSeekerSavedReflections() {
  const [items, setItems] = useState<SavedFutureSeekerReflection[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function load() {
    setBusy(true); setMessage("");
    try { setItems(await listFutureSeekerReflections()); }
    catch { setMessage("Unable to load saved reflections. Please try again."); }
    finally { setBusy(false); }
  }

  async function remove(id: string) {
    if (deletingId) return;
    setDeletingId(id); setMessage("");
    try {
      await deleteFutureSeekerReflection(id);
      setItems(previous => previous?.filter(item => item.id !== id) ?? null);
      setMessage("Reflection deleted.");
    } catch { setMessage("Unable to delete reflection. Please try again."); }
    finally { setDeletingId(null); }
  }

  return <section className="fm-saved-reflections" aria-labelledby="fm-saved-heading">
    <h2 id="fm-saved-heading">Your saved reflections</h2>
    <p>These are illustrative learning experiences, not verified skills or career predictions.</p>
    {!getToken() ? <p>Sign in to view reflections saved to your account.</p> :
      <>
        <button type="button" className="fm-secondary-action" onClick={load} disabled={busy}>
          {busy ? "Loading…" : items === null ? "View saved reflections" : "Refresh saved reflections"}
        </button>
        {items !== null && (items.length === 0 ? <p>No saved reflections yet.</p> :
          <ul className="fm-saved-list">{items.map(item => <li key={item.id}>
            <strong>{item.careerId.replace(/-/g, " ")}</strong>
            <span>{item.completedSteps} scenario steps · {item.observedSkills.length} reflective skills</span>
            <button type="button" className="fm-text-button" disabled={deletingId !== null}
              onClick={() => remove(item.id)} aria-label={`Delete ${item.careerId} reflection`}>
              {deletingId === item.id ? "Deleting…" : "Delete reflection"}
            </button>
          </li>)}</ul>)}
      </>}
    {message && <p role="status" aria-live="polite">{message}</p>}
  </section>;
}
