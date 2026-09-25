import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Admin() {
  const [itens, setItens] = useState([]);
  useEffect(() => { api.tickets().then(setItens).catch(() => setItens([])); }, []);
  return (
    <div className="card animate-fade-in">
      <h3 style={{ margin: "0 0 12px", color: "var(--blue-500)" }}>Histórico / Tickets</h3>
      {itens.length === 0 && <div className="empty-state">Sem interações ainda.</div>}
      {itens.map((t, i) => (
        <div key={i} style={{ padding: "10px 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <div><b>{t.pergunta}</b></div>
          <div className="fonte">{t.thread} · {t.em}</div>
          <div style={{ marginTop: 4 }}>
            {t.escalado
              ? <span className="badge badge-champagne">escalado</span>
              : <span className="badge badge-green">respondido</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
