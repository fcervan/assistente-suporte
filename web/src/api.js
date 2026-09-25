const API = import.meta.env.VITE_API_URL || "http://localhost:8002";

export const token = {
  get: () => localStorage.getItem("suporte_token") || "",
  set: (t) => localStorage.setItem("suporte_token", t),
  clear: () => localStorage.removeItem("suporte_token"),
};

async function req(path, opts = {}) {
  const r = await fetch(API + path, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + token.get(), ...(opts.headers || {}) },
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export const api = {
  login: (email, senha) => req("/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) }),
  register: (nome, email, senha) => req("/auth/register", { method: "POST", body: JSON.stringify({ nome, email, senha }) }),
  me: () => req("/me"),
  chat: (mensagem, thread_id = "default") => req("/chat", { method: "POST", body: JSON.stringify({ mensagem, thread_id }) }),
  tickets: () => req("/tickets"),
};
