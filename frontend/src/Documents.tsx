import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, getToken, request } from "./auth";
import { createDocumentUploadBody, validatePdfSelection } from "./documentModel";
import "./documents.css";

type DocumentItem = { id: string; original_filename: string; mime_type: string; file_size_bytes: number; page_count: number | null; processing_status: string; processing_error_code: string | null; created_at: string; updated_at: string };
type PageItem = { page_number: number; extracted_text: string; character_count: number };
type PageList = { document_id: string; total: number; items: PageItem[] };
const auth = () => ({ Authorization: "Bearer " + getToken() });
const sizeLabel = (size: number) => size < 1024 * 1024 ? `${Math.max(1, Math.round(size / 1024))} KB` : `${(size / 1024 / 1024).toFixed(1)} MB`;
const dateLabel = (value: string) => new Date(value).toLocaleString();

function useRequireLogin() {
  const navigate = useNavigate();
  useEffect(() => { if (!getToken()) navigate("/login", { replace: true }); }, [navigate]);
}

export function DocumentsPage() {
  useRequireLogin();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dragging, setDragging] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const load = useCallback(async () => {
    if (!getToken()) return;
    setLoading(true); setError("");
    try { setDocuments(await request<DocumentItem[]>("/documents?limit=100", { headers: auth() })); }
    catch (cause) { if (cause instanceof ApiError && cause.status === 401) navigate("/login", { replace: true }); else setError(cause instanceof Error ? cause.message : "Could not load documents."); }
    finally { setLoading(false); }
  }, [navigate]);
  useEffect(() => { void load(); }, [load, refresh]);

  function accept(candidate: File | undefined) {
    setError(""); setNotice("");
    if (!candidate) return;
    const validationError = validatePdfSelection(candidate);
    if (validationError) { setFile(null); setError(validationError); return; }
    setFile(candidate);
  }
  function onFile(event: ChangeEvent<HTMLInputElement>) { accept(event.target.files?.[0]); }
  function onDrop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setDragging(false); accept(event.dataTransfer.files?.[0]); }
  async function upload() {
    if (!file || uploading) return;
    const form = createDocumentUploadBody(file);
    setUploading(true); setError(""); setNotice("");
    try {
      const item = await request<DocumentItem>("/documents", { method: "POST", headers: auth(), body: form });
      setDocuments(current => [item, ...current.filter(document => document.id !== item.id)]);
      setFile(null); if (input.current) input.current.value = "";
      setNotice(item.processing_status === "text_extraction_unavailable" ? "PDF uploaded. It contains no selectable text; scanned PDF OCR is not supported yet." : "PDF uploaded and text extracted successfully.");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) { navigate("/login", { replace: true }); return; }
      setError(cause instanceof Error ? cause.message : "Upload failed. Please try again.");
    } finally { setUploading(false); }
  }
  async function remove(document: DocumentItem) {
    if (!window.confirm(`Delete “${document.original_filename}”? This cannot be undone.`)) return;
    setError("");
    try { await request<void>(`/documents/${encodeURIComponent(document.id)}`, { method: "DELETE", headers: auth() }); setDocuments(items => items.filter(item => item.id !== document.id)); setNotice("Document deleted."); }
    catch (cause) { if (cause instanceof ApiError && cause.status === 401) navigate("/login", { replace: true }); else setError(cause instanceof Error ? cause.message : "Could not delete the document."); }
  }

  return <main className="documents-shell"><header className="documents-header"><Link to="/dashboard" className="documents-back">← Dashboard</Link><span className="documents-kicker">YOUR LEARNING LIBRARY</span><h1>Documents</h1><p>Keep your study PDFs organized and review extracted text by page.</p></header>
    <section className="documents-card" aria-labelledby="upload-heading"><div className="documents-card-heading"><div><span className="documents-kicker">PRIVATE PDF STORAGE</span><h2 id="upload-heading">Add a study document</h2></div><span className="documents-limit">PDF · up to 10 MB</span></div>
      <div className={dragging ? "document-dropzone is-dragging" : "document-dropzone"} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
        <span className="document-file-icon" aria-hidden="true">PDF</span><strong>Drop your PDF here</strong><span>or choose a file from your device</span>
        <button type="button" className="document-secondary" onClick={() => input.current?.click()}>Browse files</button>
        <input ref={input} className="document-file-input" type="file" accept="application/pdf,.pdf" onChange={onFile} aria-label="Choose PDF file" />
      </div>
      {file && <div className="document-selected"><span><strong>{file.name}</strong><small>{sizeLabel(file.size)}</small></span><button type="button" aria-label="Remove selected file" onClick={() => setFile(null)}>Remove</button></div>}
      {error && <p className="document-alert" role="alert">{error}</p>}{notice && <p className="document-success" role="status">{notice}</p>}
      <div className="document-upload-actions"><span>PDF text is processed privately and is not sent to an AI provider.</span><button type="button" className="document-primary" onClick={upload} disabled={!file || uploading}>{uploading ? "Uploading and processing…" : "Upload PDF"}</button></div>
    </section>
    <section className="documents-library" aria-labelledby="library-heading"><div className="documents-card-heading"><div><span className="documents-kicker">SAVED FOR YOU</span><h2 id="library-heading">Your documents</h2></div><button type="button" className="document-refresh" onClick={() => setRefresh(value => value + 1)} disabled={loading}>Refresh</button></div>
      {loading ? <p className="document-state" role="status">Loading your documents…</p> : documents.length === 0 ? <div className="document-empty"><span aria-hidden="true">▤</span><h3>No documents yet</h3><p>Upload a text-based PDF to see its details and page text here.</p></div> : <div className="document-list">{documents.map(document => <article className="document-row" key={document.id}><span className="document-row-icon" aria-hidden="true">PDF</span><div className="document-row-main"><Link to={`/documents/${encodeURIComponent(document.id)}`}><strong>{document.original_filename}</strong></Link><small>{sizeLabel(document.file_size_bytes)} · {document.page_count ?? "—"} pages · {dateLabel(document.created_at)}</small></div><span className={`document-status status-${document.processing_status}`}>{document.processing_status === "processed" ? "Text ready" : document.processing_status === "text_extraction_unavailable" ? "No selectable text" : "Processing issue"}</span><Link className="document-secondary" to={`/documents/${encodeURIComponent(document.id)}`}>View</Link><button type="button" className="document-delete" onClick={() => void remove(document)}>Delete</button></article>)}</div>}
    </section>
  </main>;
}

export function DocumentDetailPage() {
  useRequireLogin();
  const { documentId = "" } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [pages, setPages] = useState<PageList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pageOffset, setPageOffset] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    Promise.all([
      request<DocumentItem>(`/documents/${encodeURIComponent(documentId)}`, { headers: auth() }),
      request<PageList>(`/documents/${encodeURIComponent(documentId)}/pages?limit=5&offset=${pageOffset}`, { headers: auth() }),
    ]).then(([item, pageData]) => { if (active) { setDocument(item); setPages(pageData); } })
      .catch(cause => { if (active) { if (cause instanceof ApiError && cause.status === 401) navigate("/login", { replace: true }); else setError(cause instanceof Error ? cause.message : "Could not load this document."); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [documentId, navigate, pageOffset]);
  if (loading) return <main className="documents-shell"><p className="document-state" role="status">Loading document…</p></main>;
  if (error || !document) return <main className="documents-shell"><Link to="/documents" className="documents-back">← Documents</Link><p className="document-alert" role="alert">{error || "Document not found."}</p></main>;
  return <main className="documents-shell"><Link to="/documents" className="documents-back">← All documents</Link><header className="documents-header document-detail-header"><span className="documents-kicker">DOCUMENT DETAILS</span><h1>{document.original_filename}</h1><p>{sizeLabel(document.file_size_bytes)} · Uploaded {dateLabel(document.created_at)} · {document.page_count ?? 0} pages</p><span className={`document-status status-${document.processing_status}`}>{document.processing_status === "processed" ? "Text ready" : "No selectable text"}</span></header>
    {document.processing_status === "text_extraction_unavailable" ? <div className="document-empty"><h2>No selectable text found</h2><p>This PDF may be scanned or image-only. OCR is not supported yet.</p></div> : <section className="documents-card"><div className="documents-card-heading"><div><span className="documents-kicker">EXTRACTED CONTENT</span><h2>Page text</h2></div><span className="documents-limit">{pages?.total ?? 0} pages</span></div>{pages?.items.length ? <div className="document-pages">{pages.items.map(page => <article className="document-page" key={page.page_number}><h3>Page {page.page_number}<small>{page.character_count} characters</small></h3><pre>{page.extracted_text || "No text was extracted from this page."}</pre></article>)}</div> : <p className="document-empty-copy">No page text is available.</p>}
      {(pages?.total ?? 0) > 5 && <div className="document-pagination"><button type="button" disabled={pageOffset === 0} onClick={() => setPageOffset(Math.max(0, pageOffset - 5))}>Previous pages</button><span>Pages {pageOffset + 1}–{Math.min(pageOffset + 5, pages?.total ?? 0)}</span><button type="button" disabled={pageOffset + 5 >= (pages?.total ?? 0)} onClick={() => setPageOffset(pageOffset + 5)}>Next pages</button></div>}
    </section>}</main>;
}
