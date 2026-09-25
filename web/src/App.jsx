import { useEffect, useState } from "react";
import "./tokens.css";
import Login from "./pages/Login.jsx";
import Chat from "./pages/Chat.jsx";
import Ingest from "./pages/Ingest.jsx";
import Admin from "./pages/Admin.jsx";
import Usuarios from "./pages/Usuarios.jsx";
import Observabilidade from "./pages/Observabilidade.jsx";
import { api, token } from "./api.js";

const NAV_BASE = [
  ["chat", "Chat", "⭡"],
  ["ingest", "Enviar docs", "⊕"],
  ["admin", "Tickets", "◤"],
];
const NAV_ADMIN = [
  ["usuarios", "Usuários", "⚇"],
  ["obs", "Observabilidade", "◉"],
];

export default function App() {
  const [logado, setLogado] = useState(!!token.get());
  const [aba, setAba] = useState("chat");
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("suporte_sb_collapsed") === "1");
  const [role, setRole] = useState("");

  useEffect(() => {
    if (!logado) return;
    api.me().then((m) => setRole(m.role || "")).catch(() => setRole(""));
  }, [logado]);

  function toggleCollapse() {
    setCollapsed((c) => {
      localStorage.setItem("suporte_sb_collapsed", c ? "0" : "1");
      return !c;
    });
  }

  if (!logado) {
    return (
      <div className="stage">
        <div className="panel" style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--sp-5)" }}>
          <Login onOk={() => setLogado(true)} />
        </div>
      </div>
    );
  }

  const NAV = role === "admin" ? [...NAV_BASE, ...NAV_ADMIN] : NAV_BASE;
  if (role !== "admin" && (aba === "usuarios" || aba === "obs")) setAba("chat");

  return (
    <div className="stage">
      <div className="panel" style={{ display: "flex", gap: 0, padding: 0, overflow: "hidden" }}>
        <aside className={`sidebar ${open ? "open" : ""} ${collapsed ? "collapsed" : ""}`} style={{ width: 240, flexShrink: 0, padding: "var(--sp-5) var(--sp-3)", display: "flex", flexDirection: "column" }}>
          <div style={{ position: "relative", zIndex: 1, display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
            <div className="brand-text" style={{ minWidth: 0 }}>
              <h1 style={{ fontSize: 15, fontWeight: 700, color: "var(--blue-500)", margin: 0, letterSpacing: "-0.01em" }}>
                Suporte TI
              </h1>
              <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "4px 0 0" }}>
                Assistente técnico
              </p>
            </div>
            <button className="collapse-btn" title={collapsed ? "Expandir menu" : "Recolher menu (só ícones)"} onClick={toggleCollapse}>
              {collapsed ? "»" : "«"}
            </button>
          </div>
          <nav style={{ flex: 1, marginTop: "var(--sp-4)", display: "flex", flexDirection: "column", gap: 4, position: "relative", zIndex: 1 }}>
            {NAV.map(([k, label, icon]) => (
              <a key={k} href="#" title={label} className={`nav-item ${aba === k ? "active" : ""}`}
                 onClick={(e) => { e.preventDefault(); setAba(k); setOpen(false); }}>
                <span style={{ fontSize: "var(--ic-sm)", opacity: 0.7 }}>{icon}</span>
                <span className="nav-label">{label}</span>
              </a>
            ))}
            <a href="#" title="Sair" className="nav-item"
               onClick={(e) => { e.preventDefault(); token.clear(); setLogado(false); }}>
              <span style={{ fontSize: "var(--ic-sm)", opacity: 0.7 }}>{"⏻"}</span>
              <span className="nav-label">Sair</span>
            </a>
          </nav>
          <div className="sidebar-foot" style={{ position: "relative", zIndex: 1, paddingTop: "var(--sp-3)", borderTop: "var(--b-subtle) solid rgba(255,255,255,0.06)" }}>
            <p style={{ fontSize: 10, color: "var(--text-disabled)", margin: 0 }}>v0.2.0</p>
          </div>
        </aside>

        {open && <button className="sidebar-backdrop open" aria-label="Fechar menu" onClick={() => setOpen(false)} />}

        <main style={{ flex: 1, minWidth: 0, overflow: "auto", padding: "var(--sp-5)", position: "relative", zIndex: 1 }}>
          <div className="mobile-header">
            <button className="hamburger-btn" aria-label="Abrir menu" onClick={() => setOpen(true)}>{"☰"}</button>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--blue-500)", margin: 0 }}>Suporte TI</h1>
          </div>
          {aba === "chat" && <Chat />}
          {aba === "ingest" && <Ingest />}
          {aba === "admin" && <Admin />}
          {aba === "usuarios" && role === "admin" && <Usuarios />}
          {aba === "obs" && role === "admin" && <Observabilidade />}
        </main>
      </div>
    </div>
  );
}
