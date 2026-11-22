"""HTTP API.

Run with: uv run uvicorn manger.entrypoints.fastapi_app:create_app --factory
"""

import logging
import os
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from dotenv import dotenv_values
from fastapi import Depends, FastAPI, File, Form, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from manger.bootstrap import bootstrap
from manger.domain import StorageProvider, commands, events
from manger.infra.db.uow import SqlAlchemyUnitOfWork
from manger.services.unit_of_work import AbstractUnitOfWork
from manger.infra.mq import AbstractMessagePublisher, RabbitMqPublisher
from manger.infra.storage import AbstractStorage, LocalStorage
from manger.services.commands_handlers import (
    COMMAND_HANDLERS,
    InvalidCredentials,
    StorageNotFound,
    UnknownBook,
    UnknownUser,
    UnsupportedFileType,
    UsernameTaken,
)
from manger.services.events_handlers import EVENT_HANDLERS, publish_parse, store_file
from manger.services.messagebus import MessageBus
from manger.view import get_book_status, get_books, get_user_data


class SignUpRequest(BaseModel):
    name: str
    username: str
    password: str


class SignInRequest(BaseModel):
    username: str
    password: str


class UserIdResponse(BaseModel):
    user_id: UUID


class BookIdResponse(BaseModel):
    book_id: UUID


class BookStatusResponse(BaseModel):
    book_id: UUID
    name: str
    is_parsed: bool
    viewable: bool


_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class BookResponse(BaseModel):
    book_id: UUID
    name: str
    storage_provider: StorageProvider
    storage_key: str


class UserDataResponse(BaseModel):
    user_id: UUID
    name: str
    username: str
    books: list[BookResponse]


_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw and _ENV_FILE.is_file():
        raw = (dotenv_values(_ENV_FILE).get("CORS_ORIGINS") or "").strip()
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if not origins:
        raise RuntimeError(f"CORS_ORIGINS is missing from the environment or {_ENV_FILE}")
    return origins


ERROR_STATUS = {
    ValueError: status.HTTP_400_BAD_REQUEST,
    InvalidCredentials: status.HTTP_401_UNAUTHORIZED,
    UnknownUser: status.HTTP_404_NOT_FOUND,
    UnknownBook: status.HTTP_404_NOT_FOUND,
    StorageNotFound: status.HTTP_404_NOT_FOUND,
    UsernameTaken: status.HTTP_409_CONFLICT,
    UnsupportedFileType: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
}


def create_app(
    uow_factory: Callable[[], AbstractUnitOfWork] | None = None,
    storage: AbstractStorage | None = None,
    publisher: AbstractMessagePublisher | None = None,
) -> FastAPI:
    if uow_factory is None:
        logging.basicConfig(level=logging.INFO)
        bootstrap()
        uow_factory = SqlAlchemyUnitOfWork

    file_storage = storage or LocalStorage()
    message_publisher = publisher or RabbitMqPublisher()
    app = FastAPI(title="manger")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_bus() -> MessageBus:
        # One bus and unit of work per request: both keep per-request state.
        # Store and parse use the app's storage and publisher so tests can
        # point them at a temp directory and an in-memory publisher.
        event_handlers = {
            event_type: list(handlers) for event_type, handlers in EVENT_HANDLERS.items()
        }
        event_handlers[events.StoreFile] = [lambda event: store_file(event, file_storage)]
        event_handlers[events.ParseBook] = [
            lambda event: publish_parse(event, message_publisher)
        ]
        return MessageBus(uow_factory(), event_handlers, COMMAND_HANDLERS)

    def get_uow() -> AbstractUnitOfWork:
        return uow_factory()

    # Plain `def` routes: FastAPI runs them in a thread pool, which suits the
    # synchronous SQLAlchemy session.

    @app.post("/sign_up", status_code=status.HTTP_201_CREATED)
    def sign_up(body: SignUpRequest, bus: MessageBus = Depends(get_bus)) -> UserIdResponse:
        user_id = bus.handle(commands.SignUp(body.name, body.username, body.password))
        return UserIdResponse(user_id=user_id)

    @app.post("/sign_in")
    def sign_in(body: SignInRequest, bus: MessageBus = Depends(get_bus)) -> UserIdResponse:
        user_id = bus.handle(commands.SignIn(body.username, body.password))
        return UserIdResponse(user_id=user_id)

    @app.post("/users/{user_id}/books", status_code=status.HTTP_201_CREATED)
    def add_book(
        user_id: UUID,
        file: UploadFile = File(),
        storage_provider: StorageProvider = Form(),
        name: str | None = Form(default=None),
        bus: MessageBus = Depends(get_bus),
    ) -> BookIdResponse:
        filename = file.filename or ""
        try:
            content = file.file.read()
        finally:
            file.file.close()
        book_name = (name or "").strip() or Path(filename).stem
        book_id = bus.handle(
            commands.AddBook(user_id, book_name, filename, storage_provider, content)
        )
        return BookIdResponse(book_id=book_id)

    @app.get("/users/{user_id}")
    def user_data(
        user_id: UUID, uow: AbstractUnitOfWork = Depends(get_uow)
    ) -> UserDataResponse:
        user = get_user_data(user_id, uow)
        if user is None:
            raise UnknownUser(f"User {user_id} not found")
        return UserDataResponse(
            user_id=user["user_id"],
            name=user["name"],
            username=user["username"],
            books=[BookResponse(**book) for book in get_books(user_id, uow)],
        )

    @app.get("/users/{user_id}/books/{book_id}")
    def book_status(
        user_id: UUID, book_id: UUID, uow: AbstractUnitOfWork = Depends(get_uow)
    ) -> BookStatusResponse:
        user_exists, book = get_book_status(user_id, book_id, uow)
        if not user_exists:
            raise UnknownUser(f"User {user_id} not found")
        if book is None:
            raise UnknownBook(f"Book {book_id} not found for this user")
        return BookStatusResponse(**book)

    @app.get("/users/{user_id}/books/{book_id}/file")
    def book_file(
        user_id: UUID, book_id: UUID, uow: AbstractUnitOfWork = Depends(get_uow)
    ) -> FileResponse:
        user_exists, book = get_book_status(user_id, book_id, uow)
        if not user_exists:
            raise UnknownUser(f"User {user_id} not found")
        if book is None:
            raise UnknownBook(f"Book {book_id} not found for this user")
        if book["storage_provider"] != StorageProvider.LOCAL.value or not isinstance(
            file_storage, LocalStorage
        ):
            raise StorageNotFound("Book file is not on local storage")
        try:
            path = file_storage.resolve(book["storage_key"])
        except FileNotFoundError as exc:
            raise StorageNotFound("Book file not found") from exc
        return FileResponse(
            path,
            media_type=_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
            filename=path.name,
            content_disposition_type="inline",
        )

    @app.delete("/users/{user_id}/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
    def remove_book(
        user_id: UUID, book_id: UUID, bus: MessageBus = Depends(get_bus)
    ) -> Response:
        bus.handle(commands.RemoveBook(user_id, book_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    for error, code in ERROR_STATUS.items():

        def handler(request: Request, exc: Exception, code: int = code) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=code)

        app.add_exception_handler(error, handler)

    return app
