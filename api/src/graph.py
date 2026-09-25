"""Grafo LangGraph: triagem -> rewrite -> retrieve -> grade -> gerar/escalate.

Fase 2: memória conversacional (últimas 10 msgs + resumo compactado da thread).
Evolução do agente_de_suporte_langgraph.ipynb com RAG híbrido + citação.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

SYSTEM = (
    "Você é o assistente de suporte técnico de TI (PT-BR). "
    "Responda APENAS com base nos trechos recuperados. "
    "Use o HISTÓRICO e o RESUMO só como contexto da conversa (não como fonte factual). "
    "Cite as fontes [fonte]. Se não houver base suficiente, diga que não sabe "
    "e peça escalação humana. Nunca invente comandos ou procedimentos."
)

RESUMO_SYSTEM = (
    "Você resume conversas de suporte (PT-BR) em até 150 palavras: "
    "fatos (nomes, sistemas, erros, versões), o que já foi tentado e pendências. "
    "Texto corrido, sem inventar nada."
)

REWRITE_SYSTEM = (
    "Você reescreve a última pergunta do usuário como uma busca autocontida (PT-BR), "
    "incorporando entidades do RESUMO e do HISTÓRICO (ex: 'ele' -> nome do sistema). "
    "Responda com UMA frase, sem explicações."
)


class State(TypedDict, total=False):
    pergunta: str
    categoria: str
    urgente: bool
    busca: str
    historico: list
    resumo: str
    trechos: list
    usar_trechos: bool
    resposta: str
    escalado: bool
    provedor: str


def triagem(state: State) -> State:
    q = state["pergunta"].lower()
    if any(k in q for k in ["senha", "login", "acesso", "vpn", "rede", "impressora", "email"]):
        cat = "infra"
    elif any(k in q for k in ["erro", "bug", "tela", "sistema", "api", "banco"]):
        cat = "sistema"
    else:
        cat = "geral"
    urgente = any(
        k in q for k in ["urgente", "parado", "produção parada", "producao parada", "crítico"]
    )
    return {**state, "categoria": cat, "urgente": urgente}


def reescrever(state: State) -> State:
    """Condensa follow-ups ('e ele?', 'e o passo 2?') em query autocontida."""
    hist = state.get("historico") or []
    resumo = (state.get("resumo") or "").strip()
    if not hist and not resumo:
        return {**state, "busca": state["pergunta"]}
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from . import llm_client

        llm = llm_client.get_llm(verbose=False)
        htxt = formatar_historico(hist[-6:], limite=400)
        msg = llm.invoke([
            SystemMessage(content=REWRITE_SYSTEM),
            HumanMessage(content=f"RESUMO: {resumo[:800]}\nHISTÓRICO:\n{htxt}\n"
                                 f"PERGUNTA: {state['pergunta']}"),
        ])
        busca = (msg.content or "").strip().split("\n")[0][:500] or state["pergunta"]
        return {**state, "busca": busca}
    except Exception:
        return {**state, "busca": state["pergunta"]}


def recuperar(state: State) -> State:
    try:
        from . import vector_qdrant

        trechos = vector_qdrant.buscar(state.get("busca") or state["pergunta"], top_k=6)
    except Exception:
        trechos = []  # Qdrant fora do ar: segue p/ escalate sem quebrar
    return {**state, "trechos": trechos}


def grade(state: State) -> str:
    if state.get("urgente") and not state.get("trechos"):
        return "escalar"
    if not state.get("trechos"):
        return "escalar"
    return "gerar"


def formatar_historico(historico: list | None, limite: int = 600) -> str:
    linhas = []
    for m in historico or []:
        quem = "Usuário" if (m.get("role") == "user") else "Assistente"
        linhas.append(f"{quem}: {(m.get('content') or '')[:limite]}")
    return "\n".join(linhas)


def gerar(state: State) -> State:
    try:
        from . import llm_client

        llm = llm_client.get_llm(verbose=False)
        provedor = "llm"
    except Exception:
        # Sem chave/LLM: resposta extrativa simples (não quebra o chat)
        trechos = state.get("trechos", [])[:2]
        txt = "\n\n".join(f"[{t.get('fonte','doc')}] {t.get('texto','')[:600]}" for t in trechos)
        fontes = "; ".join(t.get("fonte", "doc") for t in trechos) or "base local"
        return {**state, "resposta": f"Baseado na base ({fontes}):\n\n{txt}",
                "escalado": False, "provedor": "extrativo"}
    ctx = "\n\n".join(
        f"[{t.get('fonte','doc')}] {t.get('texto','')[:900]}" for t in state.get("trechos", [])[:4]
    )
    resumo = (state.get("resumo") or "").strip()
    htxt = formatar_historico((state.get("historico") or [])[-10:])
    from langchain_core.messages import HumanMessage, SystemMessage

    humano = (
        (f"RESUMO DA CONVERSA:\n{resumo[:1200]}\n\n" if resumo else "")
        + (f"HISTÓRICO RECENTE:\n{htxt}\n\n" if htxt else "")
        + f"TRECHOS:\n{ctx}\n\nPERGUNTA ATUAL: {state['pergunta']}"
    )
    msg = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=humano)])
    return {**state, "resposta": msg.content, "escalado": False, "provedor": provedor}


def gerar_resumo(resumo_antigo: str, ultimas: list[dict]) -> str:
    """Compacta a thread: resumo_antigo + últimas 10 msgs -> novo resumo (falha = mantém)."""
    htxt = formatar_historico(ultimas[-10:], limite=600)
    if not htxt.strip():
        return resumo_antigo or ""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from . import llm_client

        llm = llm_client.get_llm(verbose=False)
        msg = llm.invoke([
            SystemMessage(content=RESUMO_SYSTEM),
            HumanMessage(content=f"RESUMO ANTERIOR:\n{(resumo_antigo or '')[:1500]}\n\n"
                                 f"NOVAS MENSAGENS:\n{htxt}"),
        ])
        return (msg.content or "").strip()[:4000] or (resumo_antigo or "")
    except Exception:
        return resumo_antigo or ""


def escalar(state: State) -> State:
    return {**state,
            "resposta": "Não encontrei base suficiente. Abri escalação para o time humano "
                        "— descreva prints/erro/horário para agilizar.",
            "escalado": True, "provedor": "regra"}


def build_graph():
    g = StateGraph(State)
    g.add_node("triagem", triagem)
    g.add_node("reescrever", reescrever)
    g.add_node("recuperar", recuperar)
    g.add_node("gerar", gerar)
    g.add_node("escalar", escalar)
    g.set_entry_point("triagem")
    g.add_edge("triagem", "reescrever")
    g.add_edge("reescrever", "recuperar")
    g.add_conditional_edges("recuperar", grade, {"gerar": "gerar", "escalar": "escalar"})
    g.add_edge("gerar", END)
    g.add_edge("escalar", END)
    return g.compile()


_graph = None


def responder(pergunta: str, historico: list | None = None, resumo: str = "") -> dict:
    global _graph
    if _graph is None:
        _graph = build_graph()
    out = _graph.invoke({"pergunta": pergunta, "historico": historico or [],
                         "resumo": resumo or ""})
    return {"resposta": out.get("resposta", ""), "fontes": out.get("trechos", [])[:4],
            "escalado": bool(out.get("escalado")), "provedor": out.get("provedor", ""),
            "busca": out.get("busca", pergunta)}
