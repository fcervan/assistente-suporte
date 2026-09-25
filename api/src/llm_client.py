"""Cliente LLM com fallback: Groq -> Ollama Cloud -> OpenRouter (Groq primeiro por latência)."""

import os

DEFAULTS = {
    "GROQ_MODEL": "openai/gpt-oss-20b",
    "OLLAMA_CLOUD_MODEL": "nemotron-3-nano:30b-cloud",
    "OPENROUTER_MODEL": "google/gemma-4-31b-it",
}


def effective_models() -> dict:
    """Retorna provedor -> modelo efetivo dado o os.environ atual (sem criar cliente)."""
    return {
        "groq": os.getenv("GROQ_MODEL", DEFAULTS["GROQ_MODEL"]),
        "ollama": os.getenv("OLLAMA_CLOUD_MODEL", DEFAULTS["OLLAMA_CLOUD_MODEL"]),
        "openrouter": os.getenv("OPENROUTER_MODEL", DEFAULTS["OPENROUTER_MODEL"]),
    }


def get_llm(verbose: bool = True):
    """Tenta Groq, depois Ollama Cloud, depois OpenRouter. Erro claro se sem chave."""
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from langchain_groq import ChatGroq

            model = os.getenv("GROQ_MODEL", DEFAULTS["GROQ_MODEL"])
            if verbose:
                print(f"LLM: Groq ({model})")
            return ChatGroq(model=model, api_key=groq_key)
        except Exception:
            pass

    ollama_key = os.getenv("OLLAMA_CLOUD_API_KEY")
    if ollama_key:
        try:
            from langchain_openai import ChatOpenAI

            model = os.getenv("OLLAMA_CLOUD_MODEL", DEFAULTS["OLLAMA_CLOUD_MODEL"])
            if verbose:
                print(f"LLM: Ollama Cloud ({model})")
            return ChatOpenAI(
                model=model,
                api_key=ollama_key,
                base_url="https://ollama.com/v1",
            )
        except Exception:
            pass

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            from langchain_openai import ChatOpenAI

            model = os.getenv("OPENROUTER_MODEL", DEFAULTS["OPENROUTER_MODEL"])
            if verbose:
                print(f"LLM: OpenRouter ({model})")
            return ChatOpenAI(
                model=model,
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
            )
        except Exception:
            pass

    raise RuntimeError(
        "Nenhuma chave encontrada. Defina GROQ_API_KEY, "
        "OLLAMA_CLOUD_API_KEY ou OPENROUTER_API_KEY"
    )
