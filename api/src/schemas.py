"""Schemas Pydantic da API."""
from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    nome: str
    email: str
    senha: str = Field(min_length=6)
    role: str = "user"


class LoginIn(BaseModel):
    email: str
    senha: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatIn(BaseModel):
    mensagem: str
    thread_id: str = "default"


class Fonte(BaseModel):
    fonte: str = ""
    pagina: int | None = None
    score: float = 0.0


class ChatOut(BaseModel):
    resposta: str
    fontes: list[Fonte] = []
    escalado: bool = False
    provedor: str = ""
