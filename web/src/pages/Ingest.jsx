import { useRef, useState } from "react";

const ACCEPT = ".pdf,.docx,.pptx,.xlsx,.csv,.html,.xml,.txt,.md";

export default function Ingest() {
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [files, setFiles] = useState([]);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  function addList(list) {
    const arr = Array.from(list || []);
    if (!arr.length) return;
    setFiles((f) => [...f, ...arr]);
  }

  function onDrop(e) {
    e.preventDefault(); setDrag(false);
    addList(e.dataTransfer.files);
  }

  async function processar(e) {
    e.preventDefault();
    const sel = inputRef.current?.files?.length ? Array.from(inputRef.current.files) : files;
    if (!sel.length) { setStatus("Selecione ou arraste ao menos 1 arquivo."); return; }
    setLoading(true); setStatus("Processando via Docling...");
    const fd = new FormData();
    for (const f of sel) fd.append("files", f);
    const t = localStorage.getItem("suporte_token") || "";
    try {
      const r = await fetch((import.meta.env.VITE_API_URL || "http://localhost:8002") + "/ingest",
        { method: "POST", headers: { Authorization: "Bearer " + t }, body: fd });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || JSON.stringify(j));
      setStatus(`OK: ${j.arquivos} arquivo(s), ${j.chunks} chunks indexados.`);
      setFiles([]);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      setStatus("Falha — " + String(err.message || "verifique a API.").slice(0, 300));
    }
    setLoading(false);
  }

  function remover(i) {
    setFiles((f) => f.filter((_, j) => j !== i));
  }

  function fmtSize(n) {
    if (n > 1048576) return (n / 1048576).toFixed(1) + " MB";
    return Math.max(1, Math.round(n / 1024)) + " KB";
  }

  return (
    <div className="card animate-fade-in">
      <h3 style={{ margin: "0 0 4px", color: "var(--blue-500)" }}>Ingestão (admin) — Docling</h3>
      <p className="fonte" style={{ margin: "0 0 16px" }}>PDF/DOCX/XLSX/CSV/HTML/XML → markdown → chunk → Qdrant. Clique ou arraste os arquivos.</p>
      <form onSubmit={processar} style={{ display: "grid", gap: 12 }}>
        <div className={`dropzone ${drag ? "active" : ""}`}
             onClick={() => inputRef.current?.click()}
             onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
             onDragLeave={() => setDrag(false)}
             onDrop={onDrop}>
          {drag ? "Solte os arquivos aqui…" : "Arraste arquivos para cá ou clique para selecionar"}
          <div className="fonte">PDF · DOCX · PPTX · XLSX · CSV · HTML · XML · TXT · MD</div>
        </div>
        <input ref={inputRef} type="file" name="arquivos" multiple accept={ACCEPT}
               style={{ display: "none" }} onChange={(e) => addList(e.target.files)} />
        {files.length > 0 && (
          <div>
            {files.map((f, i) => (
              <div key={i} className="file-row">
                <span title={f.name} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name} · {fmtSize(f.size)}</span>
                <button type="button" className="btn-secondary" style={{ padding: "2px 10px" }} onClick={() => remover(i)}>✕</button>
              </div>
            ))}
          </div>
        )}
        <div><button className="btn-primary" type="submit" disabled={loading}>{loading && <span className="spinner" />}Processar</button></div>
        {status && <span className="fonte">{status}</span>}
      </form>
    </div>
  );
}
