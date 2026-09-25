const API = import.meta.env.VITE_API_URL || "http://localhost:8002";

export const token = {
  get: () => localStorage.getItem("suporte_token") || "",
  set: (t) => localStorage.setItem("suporte_token", t),
  clear: () => localStorage.removeItem("suporte_token"),
};

export const threadAtual = {
  get: () => localStorage.getItem("suporte_thread") || "",
  set: (t) => (t ? localStorage.setItem("suporte_thread", t) : localStorage.removeItem("suporte_thread")),
};

async function req(path, opts = {}) {
  const r = await fetch(API + path, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + token.get(), ...(opts.headers || {}) },
  });
  if (!r.ok) throw new Error(await r.text());
  if (r.status === 204) return null;
  return r.json();
}

export const api = {
  login: (email, senha) => req("/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) }),
  register: (nome, email, senha) => req("/auth/register", { method: "POST", body: JSON.stringify({ nome, email, senha }) }),
  me: () => req("/me"),
  chat: (mensagem, thread_id = "") => req("/chat", { method: "POST", body: JSON.stringify({ mensagem, thread_id: thread_id || "" }) }),
  tickets: () => req("/tickets"),
  threads: () => req("/threads"),
  criarThread: () => req("/threads", { method: "POST", body: JSON.stringify({}) }),
  threadMsgs: (id) => req(`/threads/${id}`),
  renomearThread: (id, titulo) => req(`/threads/${id}`, { method: "PATCH", body: JSON.stringify({ titulo }) }),
  apagarThread: (id) => req(`/threads/${id}`, { method: "DELETE" }),
};
