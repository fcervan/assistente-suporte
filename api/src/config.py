"""Config central (env)."""
import os

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "suporte_ti")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./data/duckdb/tickets.duckdb")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-trocar")
JWT_ALG = "HS256"
JWT_MINUTES = int(os.getenv("JWT_MINUTES", "480"))
EMBED_MODEL = os.getenv(
    "EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
