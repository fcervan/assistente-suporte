"""Grafo LangGraph: triagem -> retrieve -> grade -> gerar/escalate.

Evolução do agente_de_suporte_langgraph.ipynb com RAG híbrido + citação.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

SYSTEM = (
    "Você é o assistente de suporte técnico de TI (PT-BR). "
    "Responda APENAS com base nos trechos recuperados. "
    "Cite as fontes [fonte]. Se não houver base suficiente, diga que não sabe "
    "e peça escalação humana. Nunca invente comandos ou procedimentos."
)


class State(TypedDict, total=False):
    pergunta: str
    categoria: str
    urgente: bool
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


def recuperar(state: State) -> State:
    try:
        from . import vector_qdrant

        trechos = vector_qdrant.buscar(state["pergunta"], top_k=6)
    except Exception:
        trechos = []  # Qdrant fora do ar: segue p/ escalate sem quebrar
    return {**state, "trechos": trechos}


def grade(state: State) -> str:
    if state.get("urgente") and not state.get("trechos"):
        return "escalar"
    if not state.get("trechos"):
        return "escalar"
    return "gerar"


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
    from langchain_core.messages import HumanMessage, SystemMessage

    msg = llm.invoke([SystemMessage(content=SYSTEM),
                      HumanMessage(content=f"TRECHOS:\n{ctx}\n\nPERGUNTA: {state['pergunta']}")])
    return {**state, "resposta": msg.content, "escalado": False, "provedor": provedor}


def escalar(state: State) -> State:
    return {**state,
            "resposta": "Não encontrei base suficiente. Abri escalação para o time humano "
                        "— descreva prints/erro/horário para agilizar.",
            "escalado": True, "provedor": "regra"}


def build_graph():
    g = StateGraph(State)
    g.add_node("triagem", triagem)
    g.add_node("recuperar", recuperar)
    g.add_node("gerar", gerar)
    g.add_node("escalar", escalar)
    g.set_entry_point("triagem")
    g.add_edge("triagem", "recuperar")
    g.add_conditional_edges("recuperar", grade, {"gerar": "gerar", "escalar": "escalar"})
    g.add_edge("gerar", END)
    g.add_edge("escalar", END)
    return g.compile()


_graph = None


def responder(pergunta: str) -> dict:
    global _graph
    if _graph is None:
        _graph = build_graph()
    out = _graph.invoke({"pergunta": pergunta})
    return {"resposta": out.get("resposta", ""), "fontes": out.get("trechos", [])[:4],
            "escalado": bool(out.get("escalado")), "provedor": out.get("provedor", "")}
