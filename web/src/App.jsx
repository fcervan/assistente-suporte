import { useState } from "react";
import "./tokens.css";
import Login from "./pages/Login.jsx";
import Chat from "./pages/Chat.jsx";
import Ingest from "./pages/Ingest.jsx";
import Admin from "./pages/Admin.jsx";
import { token } from "./api.js";

const NAV = [
  ["chat", "Chat", "\u2B21"],
  ["ingest", "Enviar docs", "\u2295"],
  ["admin", "Tickets", "\u25E4"],
];

export default function App() {
  const [logado, setLogado] = useState(!!token.get());
  const [aba, setAba] = useState("chat");
  const [open, setOpen] = useState(false);

  if (!logado) {
    return (
      <div className="stage">
        <div className="panel" style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--sp-5)" }}>
          <Login onOk={() => setLogado(true)} />
        </div>
      </div>
    );
  }

  return (
    <div className="stage">
      <div className="panel" style={{ display: "flex", gap: 0, padding: 0, overflow: "hidden" }}>
        <aside className={`sidebar ${open ? "open" : ""}`} style={{ width: 240, flexShrink: 0, padding: "var(--sp-5) var(--sp-3)", display: "flex", flexDirection: "column" }}>
          <div style={{ position: "relative", zIndex: 1 }}>
            <h1 style={{ fontSize: 15, fontWeight: 700, color: "var(--blue-500)", margin: 0, letterSpacing: "-0.01em" }}>
              Suporte TI
            </h1>
            <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "4px 0 0" }}>
              Assistente técnico
            </p>
          </div>
          <nav style={{ flex: 1, marginTop: "var(--sp-4)", display: "flex", flexDirection: "column", gap: 4, position: "relative", zIndex: 1 }}>
            {NAV.map(([k, label, icon]) => (
              <a key={k} href="#" className={`nav-item ${aba === k ? "active" : ""}`}
                 onClick={(e) => { e.preventDefault(); setAba(k); setOpen(false); }}>
                <span style={{ fontSize: "var(--ic-sm)", opacity: 0.7 }}>{icon}</span>
                {label}
              </a>
            ))}
            <a href="#" className="nav-item"
               onClick={(e) => { e.preventDefault(); token.clear(); setLogado(false); }}>
              <span style={{ fontSize: "var(--ic-sm)", opacity: 0.7 }}>{"\u23FB"}</span>
              Sair
            </a>
          </nav>
          <div style={{ position: "relative", zIndex: 1, paddingTop: "var(--sp-3)", borderTop: "var(--b-subtle) solid rgba(255,255,255,0.06)" }}>
            <p style={{ fontSize: 10, color: "var(--text-disabled)", margin: 0 }}>v0.1.0</p>
          </div>
        </aside>

        {open && <button className="sidebar-backdrop open" aria-label="Fechar menu" onClick={() => setOpen(false)} />}

        <main style={{ flex: 1, overflow: "auto", padding: "var(--sp-5)", position: "relative", zIndex: 1 }}>
          <div className="mobile-header">
            <button className="hamburger-btn" aria-label="Abrir menu" onClick={() => setOpen(true)}>{"\u2630"}</button>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--blue-500)", margin: 0 }}>Suporte TI</h1>
          </div>
          {aba === "chat" && <Chat />}
          {aba === "ingest" && <Ingest />}
          {aba === "admin" && <Admin />}
        </main>
      </div>
    </div>
  );
}
