import { useState } from "react";
import { api, token } from "../api.js";

export default function Login({ onOk }) {
  const [email, setEmail] = useState("fcervan@local");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [loading, setLoading] = useState(false);

  async function entrar(e) {
    e.preventDefault(); setErro(""); setLoading(true);
    try {
      const r = await api.login(email, senha);
      token.set(r.access_token); onOk();
    } catch {
      setErro("Falha no login. Verifique a API e as credenciais.");
    }
    setLoading(false);
  }

  return (
    <div className="card animate-fade-in" style={{ width: 400, maxWidth: "100%" }}>
      <h2 style={{ margin: "0 0 4px", color: "var(--blue-500)", fontSize: 20 }}>Suporte TI</h2>
      <p className="fonte" style={{ margin: "0 0 16px" }}>Assistente técnico — entre para continuar</p>
      <form onSubmit={entrar} style={{ display: "grid", gap: 12 }}>
        <div>
          <label className="field-label" htmlFor="login-email">E-mail</label>
          <div className="recessed"><input id="login-email" name="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="voce@empresa.com" autoComplete="username" /></div>
        </div>
        <div>
          <label className="field-label" htmlFor="login-senha">Senha</label>
          <div className="recessed"><input id="login-senha" name="password" className="input" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} placeholder="••••••••" autoComplete="current-password" /></div>
        </div>
        <button className="btn-primary" type="submit" disabled={loading}>
          {loading && <span className="spinner" />}
          Entrar
        </button>
        {erro && <span className="fonte">{erro}</span>}
      </form>
    </div>
  );
}
