"""HTTP API.

Run with: uv run uvicorn manger.entrypoints.fastapi_app:create_app --factory
"""

import logging
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from manger.bootstrap import bootstrap
from manger.domain import StorageProvider, commands
from manger.infra.db.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork
from manger.infra.storage import AbstractStorage, LocalStorage
from manger.services.commands_handlers import (
    COMMAND_HANDLERS,
    InvalidCredentials,
    StorageNotFound,
    UnknownBook,
    UnknownUser,
    UnsupportedFileType,
    UsernameTaken,
    upload_book,
)
from manger.services.events_handlers import EVENT_HANDLERS
from manger.services.messagebus import MessageBus
from manger.view import get_books, get_user_data


class SignUpRequest(BaseModel):
    name: str
    username: str
    password: str


class SignInRequest(BaseModel):
    username: str
    password: str


class AddBookRequest(BaseModel):
    name: str
    storage_provider: StorageProvider
    storage_key: str


class UserIdResponse(BaseModel):
    user_id: UUID


class BookIdResponse(BaseModel):
    book_id: UUID


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
) -> FastAPI:
    if uow_factory is None:
        logging.basicConfig(level=logging.INFO)
        bootstrap()
        uow_factory = SqlAlchemyUnitOfWork

    file_storage = storage or LocalStorage()
    app = FastAPI(title="manger")

    def get_bus() -> MessageBus:
        # One bus and unit of work per request: both keep per-request state.
        # Upload uses the app's storage so tests can point it at a temp directory.
        handlers = dict(COMMAND_HANDLERS)
        handlers[commands.UploadBook] = lambda command, uow: upload_book(
            command, uow, file_storage
        )
        return MessageBus(uow_factory(), EVENT_HANDLERS, handlers)

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
        user_id: UUID, body: AddBookRequest, bus: MessageBus = Depends(get_bus)
    ) -> BookIdResponse:
        book_id = bus.handle(
            commands.AddBook(user_id, body.name, body.storage_provider, body.storage_key)
        )
        return BookIdResponse(book_id=book_id)

    @app.post("/users/{user_id}/books/upload", status_code=status.HTTP_201_CREATED)
    def upload(
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
            commands.UploadBook(
                user_id, book_name, filename, storage_provider, content
            )
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
