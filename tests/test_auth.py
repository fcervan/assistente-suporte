def test_auth_hash_e_token(tmp_path, monkeypatch):
    import src.config as config

    monkeypatch.setattr(config, "DUCKDB_PATH", str(tmp_path / "t.duckdb"))
    monkeypatch.setattr(config, "JWT_SECRET", "segredo-teste")
    from src import auth, duckdb_store

    duckdb_store.init_db()
    h = auth.hash_senha("admin123")
    assert auth.check_senha("admin123", h)
    user = duckdb_store.create_user("Admin", "admin@ti.local", h, "admin")
    t = auth.token(user)
    assert isinstance(t, str) and len(t) > 20
