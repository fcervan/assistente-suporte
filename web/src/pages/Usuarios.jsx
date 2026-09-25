import { useEffect, useState } from "react";
import { api } from "../api.js";

const vazio = { nome: "", email: "", senha: "", role: "user" };

export default function Usuarios() {
  const [lista, setLista] = useState([]);
  const [form, setForm] = useState(vazio);
  const [editId, setEditId] = useState(null);
  const [edit, setEdit] = useState({ nome: "", role: "user", senha: "" });
  const [msg, setMsg] = useState("");

  async function carregar() {
    try { setLista(await api.users()); }
    catch (e) { setMsg("Falha ao carregar usuários (só admin)."); }
  }
  useEffect(() => { carregar(); }, []);

  async function criar(e) {
    e.preventDefault(); setMsg("");
    try {
      await api.criarUser(form);
      setForm(vazio); setMsg("Usuário criado.");
      carregar();
    } catch (err) { setMsg("Falha ao criar: " + (err.message || "").slice(0, 200)); }
  }

  function iniciarEdicao(u) {
    setEditId(u.id);
    setEdit({ nome: u.nome, role: u.role, senha: "" });
  }

  async function salvar(id) {
    setMsg("");
    const payload = { nome: edit.nome, role: edit.role };
    if (edit.senha) payload.senha = edit.senha;
    try {
      await api.editarUser(id, payload);
      setEditId(null); setMsg("Usuário atualizado.");
      carregar();
    } catch (err) { setMsg("Falha ao salvar: " + (err.message || "").slice(0, 200)); }
  }

  async function remover(u) {
    if (!confirm(`Remover ${u.email}?`)) return;
    try { await api.removerUser(u.id); setMsg("Usuário removido."); carregar(); }
    catch (err) { setMsg("Falha ao remover: " + (err.message || "").slice(0, 200)); }
  }

  return (
    <div className="animate-fade-in" style={{ display: "grid", gap: 16 }}>
      <div className="card">
        <h3 style={{ margin: "0 0 12px", color: "var(--blue-500)" }}>Usuários (admin)</h3>
        <form onSubmit={criar} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div>
            <label className="field-label">Nome</label>
            <div className="recessed"><input className="input" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} required /></div>
          </div>
          <div>
            <label className="field-label">E-mail</label>
            <div className="recessed"><input className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></div>
          </div>
          <div>
            <label className="field-label">Senha</label>
            <div className="recessed"><input className="input" type="password" value={form.senha} onChange={(e) => setForm({ ...form, senha: e.target.value })} required /></div>
          </div>
          <div>
            <label className="field-label">Perfil</label>
            <div className="recessed">
              <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </div>
          </div>
          <button className="btn-primary" type="submit">Adicionar</button>
        </form>
        {msg && <div className="fonte" style={{ marginTop: 8 }}>{msg}</div>}
      </div>

      <div className="card" style={{ overflowX: "auto" }}>
        <table className="tbl">
          <thead><tr><th>ID</th><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Criado em</th><th>Ações</th></tr></thead>
          <tbody>
            {lista.map((u) => (
              <tr key={u.id}>
                <td>{u.id}</td>
                <td>{editId === u.id
                  ? <div className="recessed"><input className="input" value={edit.nome} onChange={(e) => setEdit({ ...edit, nome: e.target.value })} /></div>
                  : u.nome}</td>
                <td>{u.email}</td>
                <td>{editId === u.id
                  ? <div className="recessed"><select className="input" value={edit.role} onChange={(e) => setEdit({ ...edit, role: e.target.value })}><option value="user">user</option><option value="admin">admin</option></select></div>
                  : <span className={`badge ${u.role === "admin" ? "badge-champagne" : "badge-blue"}`}>{u.role}</span>}</td>
                <td>{u.criado_em || "—"}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {editId === u.id ? (
                    <>
                      <div className="recessed" style={{ marginBottom: 6 }}><input className="input" type="password" placeholder="Nova senha (opcional)" value={edit.senha} onChange={(e) => setEdit({ ...edit, senha: e.target.value })} /></div>
                      <button className="btn-primary" onClick={() => salvar(u.id)}>Salvar</button>{" "}
                      <button className="btn-secondary" onClick={() => setEditId(null)}>Cancelar</button>
                    </>
                  ) : (
                    <>
                      <button className="btn-secondary" onClick={() => iniciarEdicao(u)}>Editar</button>{" "}
                      <button className="btn-secondary" onClick={() => remover(u)}>Remover</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {lista.length === 0 && <div className="empty-state">Nenhum usuário.</div>}
      </div>
    </div>
  );
}
