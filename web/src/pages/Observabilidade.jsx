import { useEffect, useState } from "react";
import { api } from "../api.js";
import { fmtDT } from "./Chat.jsx";

export default function Observabilidade() {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [filtro, setFiltro] = useState({ limit: 100, somente_escalados: false, provedor: "" });
  const [expand, setExpand] = useState(null);
  const [msg, setMsg] = useState("");

  async function carregar() {
    setMsg("");
    try {
      setStats(await api.adminStats());
      setLogs(await api.adminLogs({
        limit: filtro.limit,
        somente_escalados: filtro.somente_escalados,
        provedor: filtro.provedor || "",
      }));
    } catch { setMsg("Falha ao carregar (só admin, API :8002)."); }
  }
  useEffect(() => { carregar(); }, []);

  return (
    <div className="animate-fade-in" style={{ display: "grid", gap: 16 }}>
      <div className="card">
        <h3 style={{ margin: "0 0 12px", color: "var(--blue-500)" }}>Observabilidade — log global (admin)</h3>
        {stats && (
          <div className="stat-grid">
            <div className="card stat-card"><div className="stat-num">{stats.total}</div><div className="stat-label">Interações</div></div>
            <div className="card stat-card"><div className="stat-num">{stats.escalados}</div><div className="stat-label">Escaladas ({stats.pct_escalado}%)</div></div>
            <div className="card stat-card"><div className="stat-num">{stats.usuarios_ativos}</div><div className="stat-label">Usuários ativos</div></div>
            {stats.por_provedor?.slice(0, 3).map((p) => (
              <div key={p.provedor} className="card stat-card"><div className="stat-num">{p.total}</div><div className="stat-label">{p.provedor}</div></div>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div>
            <label className="field-label">Provedor</label>
            <div className="recessed"><input className="input" placeholder="groq / ollama / openrouter" value={filtro.provedor} onChange={(e) => setFiltro({ ...filtro, provedor: e.target.value })} /></div>
          </div>
          <div>
            <label className="field-label">Limite</label>
            <div className="recessed"><input className="input" type="number" min={10} max={500} value={filtro.limit} onChange={(e) => setFiltro({ ...filtro, limit: Number(e.target.value) || 100 })} /></div>
          </div>
          <label style={{ fontSize: 13, color: "var(--text-mid)", display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={filtro.somente_escalados} onChange={(e) => setFiltro({ ...filtro, somente_escalados: e.target.checked })} />
            Só escalados
          </label>
          <button className="btn-primary" onClick={carregar}>Filtrar</button>
        </div>
        {msg && <div className="fonte" style={{ marginTop: 8 }}>{msg}</div>}
      </div>

      <div className="card" style={{ overflowX: "auto" }}>
        <table className="tbl">
          <thead><tr><th>Data/hora</th><th>Usuário</th><th>Pergunta → resposta</th><th>Status</th></tr></thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td style={{ whiteSpace: "nowrap" }}>{fmtDT(l.em)}</td>
                <td>{l.email}<div className="fonte">{l.thread_id}</div></td>
                <td style={{ maxWidth: 520 }}>
                  <b style={{ color: "var(--text-hi)" }}>{l.pergunta}</b>
                  <div style={{ marginTop: 4 }}>
                    {expand === l.id ? l.resposta : (l.resposta || "").slice(0, 220) + ((l.resposta || "").length > 220 ? "…" : "")}
                    {(l.resposta || "").length > 220 && (
                      <button onClick={() => setExpand(expand === l.id ? null : l.id)}
                        style={{ background: "none", border: "none", color: "var(--blue-400)", cursor: "pointer", marginLeft: 6 }}>
                        {expand === l.id ? "recolher" : "expandir"}
                      </button>
                    )}
                  </div>
                  {l.busca && <div className="fonte">busca: {l.busca}</div>}
                </td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {l.escalado ? <span className="badge badge-champagne">escalado</span> : <span className="badge badge-green">respondido</span>}
                  {l.provedor && <div style={{ marginTop: 4 }}><span className="badge badge-blue">{l.provedor}</span></div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {logs.length === 0 && <div className="empty-state">Sem logs para o filtro.</div>}
      </div>
    </div>
  );
}
