"""HTTP API.

Run with: uv run uvicorn manger.entrypoints.fastapi_app:create_app --factory --port 8001
"""

import logging
from collections.abc import Callable
from uuid import UUID

from datetime import datetime

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from manger.bootstrap import bootstrap
from manger.domain import commands
from manger.infra.db.session.uow import SessionDbUnitOfWork
from manger.services.ai_provider import AiProvider
from manger.services.commands_handlers import (
    COMMAND_HANDLERS,
    BookNotParsed,
    UnknownBook,
    UnknownSession,
    UnsupportedStorage,
    create_session,
    infer,
)
from manger.services.events_handlers import EVENT_HANDLERS
from manger.services.messagebus import MessageBus
from manger.services.session_uow import AbstractSessionUnitOfWork
from manger.services.user_uow import AbstractUserUnitOfWork
from manger.sessions_view import get_session, list_sessions


class CreateSessionRequest(BaseModel):
    user_id: UUID
    book_id: UUID


class SessionResponse(BaseModel):
    status: str
    session_id: UUID


class InferRequest(BaseModel):
    session_id: UUID
    msg: str


class InferResponse(BaseModel):
    message: str


class SessionSummary(BaseModel):
    session_id: UUID
    book_id: UUID | None
    preview: str


class HistoryMessage(BaseModel):
    turn: str
    content: str
    date: datetime


class SessionHistory(BaseModel):
    session_id: UUID
    book_id: UUID | None
    messages: list[HistoryMessage]


ERROR_STATUS = {
    ValueError: status.HTTP_400_BAD_REQUEST,
    UnknownBook: status.HTTP_404_NOT_FOUND,
    UnknownSession: status.HTTP_404_NOT_FOUND,
    BookNotParsed: status.HTTP_409_CONFLICT,
    UnsupportedStorage: status.HTTP_400_BAD_REQUEST,
}


def create_app(
    uow_factory: Callable[[], AbstractSessionUnitOfWork] | None = None,
    user_uow_factory: Callable[[], AbstractUserUnitOfWork] | None = None,
    provider: AiProvider | None = None,
    lookup_book: Callable[..., dict | None] | None = None,
    load_paragraphs: Callable[..., str] | None = None,
) -> FastAPI:
    if uow_factory is None:
        logging.basicConfig(level=logging.INFO)
        bootstrap()
        uow_factory = SessionDbUnitOfWork

    app = FastAPI(title="chatbot")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_bus() -> MessageBus:
        command_handlers = dict(COMMAND_HANDLERS)
        command_handlers[commands.CreateSession] = lambda command, uow: create_session(
            command,
            uow,
            lookup_book=lookup_book,
            load_paragraphs=load_paragraphs,
            user_uow=user_uow_factory() if user_uow_factory else None,
        )
        command_handlers[commands.Infer] = lambda command, uow: infer(
            command, uow, provider=provider
        )
        return MessageBus(uow_factory(), EVENT_HANDLERS, command_handlers)

    @app.post("/sessions", status_code=status.HTTP_201_CREATED)
    def open_session(
        body: CreateSessionRequest, bus: MessageBus = Depends(get_bus)
    ) -> SessionResponse:
        result = bus.handle(commands.CreateSession(body.user_id, body.book_id))
        return SessionResponse(status=result["status"], session_id=result["session_id"])

    def get_uow() -> AbstractSessionUnitOfWork:
        return uow_factory()

    @app.get("/users/{user_id}/sessions")
    def sessions(
        user_id: UUID, uow: AbstractSessionUnitOfWork = Depends(get_uow)
    ) -> list[SessionSummary]:
        return [SessionSummary(**row) for row in list_sessions(user_id, uow)]

    @app.get("/users/{user_id}/sessions/{session_id}")
    def session_history(
        user_id: UUID,
        session_id: UUID,
        uow: AbstractSessionUnitOfWork = Depends(get_uow),
    ) -> SessionHistory:
        session = get_session(user_id, session_id, uow)
        if session is None:
            raise UnknownSession(f"Session {session_id} not found")
        return SessionHistory(**session)

    @app.post("/infer")
    def ask(body: InferRequest, bus: MessageBus = Depends(get_bus)) -> InferResponse:
        reply = bus.handle(commands.Infer(body.session_id, body.msg))
        return InferResponse(message=reply)

    for error, code in ERROR_STATUS.items():

        def handler(request: Request, exc: Exception, code: int = code) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=code)

        app.add_exception_handler(error, handler)

    return app
