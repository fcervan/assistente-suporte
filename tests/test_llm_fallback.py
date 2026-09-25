import os


def test_fallback_sem_chave_explica():
    for k in ["GROQ_API_KEY", "OLLAMA_CLOUD_API_KEY", "OPENROUTER_API_KEY"]:
        os.environ.pop(k, None)
    from src import llm_client

    try:
        llm_client.get_llm(verbose=False)
        assert False, "deveria falhar sem chave"
    except RuntimeError as e:
        assert "GROQ_API_KEY" in str(e)


def test_modelos_efetivos():
    from src import llm_client

    m = llm_client.effective_models()
    assert set(m) == {"groq", "ollama", "openrouter"}
