from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    model: str = Field(default="auto")
    messages: list
    stream: bool = False
    tools: list | bool | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    task: str | None = None
    force_guardian: bool = False


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list
    usage: dict | None = None


class VideoIngestRequest(BaseModel):
    path: str


class AnalizarRequest(BaseModel):
    peticion: str


class SintesisRequest(BaseModel):
    peticion: str


class FaseRequest(BaseModel):
    keywords: str


class ConsultaRequest(BaseModel):
    query: str
    forzar_web: bool = False
