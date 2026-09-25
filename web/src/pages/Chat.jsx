import { useEffect, useState } from "react";
import { api, threadAtual } from "../api.js";

function bolha(m, i) {
  return (
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
  );
}

export default function Chat() {
  const [msg, setMsg] = useState("");
  const [hist, setHist] = useState([]);
  const [loading, setLoading] = useState(false);
  const [threads, setThreads] = useState([]);
  const [tid, setTid] = useState(threadAtual.get());
  const [editId, setEditId] = useState("");
  const [editTitulo, setEditTitulo] = useState("");

  async function carregarThreads(selecionar = "") {
    try {
      const lista = await api.threads();
      setThreads(lista);
      const alvo = selecionar || threadAtual.get() || lista[0]?.id || "";
      if (alvo && alvo !== tid) await abrirThread(alvo, lista);
      else if (!alvo) { setTid(""); setHist([]); }
    } catch { /* API fora do ar: mantém chat local */ }
  }

  async function abrirThread(id, lista = null) {
    setTid(id); threadAtual.set(id);
    try {
      const msgs = await api.threadMsgs(id);
      const h = [];
      for (const m of msgs) {
        if (m.pergunta) h.push({ quem: "user", texto: m.pergunta });
        if (m.resposta) h.push({ quem: "bot", texto: m.resposta, escalado: m.escalado });
      }
      setHist(h);
    } catch {
      setHist([]);
    }
    if (!lista) carregarThreadsSilenciosa();
  }

  async function carregarThreadsSilenciosa() {
    try { setThreads(await api.threads()); } catch { /* noop */ }
  }

  useEffect(() => { carregarThreads(); }, []);

  async function novaConversa() {
    setHist([]); setMsg("");
    try {
      const t = await api.criarThread();
      setTid(t.id); threadAtual.set(t.id);
      carregarThreadsSilenciosa();
    } catch {
      setTid(""); threadAtual.set("");  // offline: próxima msg cria thread no backend
    }
  }

  async function enviar(e) {
    e.preventDefault();
    if (!msg.trim() || loading) return;
    const pergunta = msg; setMsg(""); setLoading(true);
    setHist((h) => [...h, { quem: "user", texto: pergunta }]);
    try {
      const r = await api.chat(pergunta, tid);
      if (r.thread_id && r.thread_id !== tid) { setTid(r.thread_id); threadAtual.set(r.thread_id); }
      setHist((h) => [...h, { quem: "bot", texto: r.resposta, fontes: r.fontes, escalado: r.escalado }]);
      carregarThreadsSilenciosa();
    } catch {
      setHist((h) => [...h, { quem: "bot", texto: "API fora do ar (:8002). Suba com docker compose up api." }]);
    }
    setLoading(false);
  }

  async function apagar(id) {
    if (!confirm("Apagar esta conversa?")) return;
    try {
      await api.apagarThread(id);
      if (id === tid) { setTid(""); threadAtual.set(""); setHist([]); }
      carregarThreadsSilenciosa();
    } catch { alert("Falha ao apagar."); }
  }

  async function salvarTitulo(id) {
    if (!editTitulo.trim()) { setEditId(""); return; }
    try {
      await api.renomearThread(id, editTitulo.trim());
      setEditId(""); carregarThreadsSilenciosa();
    } catch { alert("Falha ao renomear."); }
  }

  return (
    <div style={{ display: "flex", gap: 12 }} className="animate-fade-in">
      <aside className="card" style={{ width: 230, flexShrink: 0, maxHeight: 560, overflow: "auto" }}>
        <button className="btn-primary" style={{ width: "100%", marginBottom: 10 }} onClick={novaConversa}>+ Nova conversa</button>
        {threads.length === 0 && <div className="empty-state">Sem conversas ainda.</div>}
        {threads.map((t) => (
          <div key={t.id} className={`nav-item ${t.id === tid ? "active" : ""}`}
               style={{ cursor: "pointer", marginBottom: 4 }} onClick={() => abrirThread(t.id)}>
            {editId === t.id ? (
              <input autoFocus value={editTitulo} onChange={(e) => setEditTitulo(e.target.value)}
                     onClick={(e) => e.stopPropagation()}
                     onBlur={() => salvarTitulo(t.id)}
                     onKeyDown={(e) => { if (e.key === "Enter") salvarTitulo(t.id); if (e.key === "Escape") setEditId(""); }}
                     style={{ width: "100%" }} />
            ) : (
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.titulo}</div>
                <div className="fonte">{t.mensagens} msgs{t.tem_resumo ? " · resumida" : ""}</div>
              </div>
            )}
            <span style={{ display: "flex", gap: 4 }}>
              <button title="Renomear" onClick={(e) => { e.stopPropagation(); setEditId(t.id); setEditTitulo(t.titulo); }}>✎</button>
              <button title="Apagar" onClick={(e) => { e.stopPropagation(); apagar(t.id); }}>🗑</button>
            </span>
          </div>
        ))}
      </aside>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="card" style={{ minHeight: 320, maxHeight: 560, overflow: "auto" }}>
          {hist.length === 0 && <div className="empty-state">Pergunte algo de TI — ex: como funciona a autenticação na API SmartLabel?</div>}
          {hist.map(bolha)}
          {loading && <div className="msg-row bot"><div className="bubble-bot"><span className="spinner" /> Gerando resposta…</div></div>}
        </div>
        <form onSubmit={enviar} style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <div className="recessed" style={{ flex: 1 }}>
            <input className="input" value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Digite sua dúvida de TI..." />
          </div>
          <button className="btn-primary" type="submit" disabled={loading}>Enviar</button>
        </form>
      </div>
    </div>
  );
}
