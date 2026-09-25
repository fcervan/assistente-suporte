import { useState } from "react";

export default function Ingest() {
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    const files = e.target.arquivos.files;
    if (!files.length) return;
    setLoading(true); setStatus("Processando via Docling...");
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    const t = localStorage.getItem("suporte_token") || "";
    try {
      const r = await fetch((import.meta.env.VITE_API_URL || "http://localhost:8002") + "/ingest",
        { method: "POST", headers: { Authorization: "Bearer " + t }, body: fd });
      const j = await r.json();
      setStatus(`OK: ${j.arquivos} arquivo(s), ${j.chunks} chunks indexados.`);
    } catch {
      setStatus("Falha — verifique a API.");
    }
    setLoading(false);
  }

  return (
    <div className="card animate-fade-in">
      <h3 style={{ margin: "0 0 4px", color: "var(--blue-500)" }}>Ingestão (admin) — Docling</h3>
      <p className="fonte" style={{ margin: "0 0 16px" }}>PDF/DOCX/XLSX/CSV/HTML/XML → markdown → chunk → Qdrant.</p>
      <form onSubmit={enviar} style={{ display: "grid", gap: 12 }}>
        <input type="file" name="arquivos" multiple accept=".pdf,.docx,.pptx,.xlsx,.csv,.html,.xml,.txt,.md" style={{ color: "var(--text-mid)", fontSize: 13 }} />
        <div><button className="btn-primary" type="submit" disabled={loading}>{loading && <span className="spinner" />}Processar</button></div>
        {status && <span className="fonte">{status}</span>}
      </form>
    </div>
  );
}
