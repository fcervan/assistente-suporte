import { useState } from "react";
import { api } from "../api.js";

export default function Chat() {
  const [msg, setMsg] = useState("");
  const [hist, setHist] = useState([]);
  const [loading, setLoading] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    if (!msg.trim() || loading) return;
    const pergunta = msg; setMsg(""); setLoading(true);
    setHist((h) => [...h, { quem: "user", texto: pergunta }]);
    try {
      const r = await api.chat(pergunta);
      setHist((h) => [...h, { quem: "bot", texto: r.resposta, fontes: r.fontes, escalado: r.escalado }]);
    } catch {
      setHist((h) => [...h, { quem: "bot", texto: "API fora do ar (:8002). Suba com docker compose up api." }]);
    }
    setLoading(false);
  }

  return (
    <div className="animate-fade-in">
      <div className="card" style={{ minHeight: 320 }}>
        {hist.length === 0 && <div className="empty-state">Pergunte algo de TI — ex: como funciona a autenticação na API SmartLabel?</div>}
        {hist.map((m, i) => (
          <div key={i} className={`msg-row ${m.quem === "user" ? "user" : "bot"}`}>
            <div className={m.quem === "user" ? "bubble-user" : "bubble-bot"}>
              <div>{m.texto}</div>
              {m.fontes?.map((f, j) => (
                <div key={j} style={{ marginTop: 6 }}>
                  <span className="badge badge-blue">{f.fonte}{f.pagina ? ` · p.${f.pagina}` : ""} · {f.score}</span>
                </div>
              ))}
              {m.escalado && <div style={{ marginTop: 6 }}><span className="badge badge-champagne">Escalado ao time humano</span></div>}
            </div>
          </div>
        ))}
        {loading && <div className="msg-row bot"><div className="bubble-bot"><span className="spinner" /></div></div>}
      </div>
      <form onSubmit={enviar} style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <div className="recessed" style={{ flex: 1 }}>
          <input className="input" value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Digite sua dúvida de TI..." />
        </div>
        <button className="btn-primary" type="submit" disabled={loading}>Enviar</button>
      </form>
    </div>
  );
}
