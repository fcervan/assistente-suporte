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
    thread_id: str = "default"


class ThreadOut(BaseModel):
    id: str
    titulo: str = "Nova conversa"
    tem_resumo: bool = False
    atualizado_em: str = ""
    mensagens: int = 0


class ThreadRenameIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=80)


class ThreadCreateIn(BaseModel):
    titulo: str = "Nova conversa"


class ThreadMsg(BaseModel):
    pergunta: str = ""
    resposta: str = ""
    escalado: bool = False
    em: str = ""


class UserOut(BaseModel):
    id: int
    nome: str
    email: str
    role: str = "user"
    criado_em: str = ""


class UserCreateIn(BaseModel):
    nome: str
    email: str
    senha: str = Field(min_length=6)
    role: str = "user"


class UserUpdateIn(BaseModel):
    nome: str | None = None
    role: str | None = None
    senha: str | None = None


class AdminLog(BaseModel):
    id: int = 0
    user_id: int = 0
    email: str = ""
    thread_id: str = ""
    pergunta: str = ""
    resposta: str = ""
    escalado: bool = False
    provedor: str = ""
    busca: str = ""
    em: str = ""
