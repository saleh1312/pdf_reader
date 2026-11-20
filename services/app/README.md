# manger

The pdf_reader app service: users sign up, sign in, and manage their books.
Requests go through a message bus to command handlers, which use a unit of work
over PostgreSQL (SQLAlchemy).

All commands below run from this directory (`services/app`) and use
[uv](https://docs.astral.sh/uv/), which creates and uses `.venv` automatically.

## Setup

```bash
uv sync
```

Start PostgreSQL (needed for the API and for `--real` tests):

```bash
docker compose -f db/lunch/docker-compose.yml up -d
```

See [db/lunch/README.md](db/lunch/README.md) for database details.

The app connects to
`postgresql+psycopg://postgres:postgres@localhost:5432/pdf_reader` by default.
To use another database, set `DATABASE_URL`:

```bash
# bash
export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname"
# PowerShell
$env:DATABASE_URL = "postgresql+psycopg://user:pass@host:5432/dbname"
```

Tables are created automatically on startup if they don't exist.

## Running the tests

```bash
uv run pytest
```

By default the service and API tests use an in-memory fake unit of work, so no
database is needed. The one exception is `tests/infra`, which always uses
PostgreSQL and is skipped if it isn't reachable.

| Option    | Effect                                                                                |
| --------- | ------------------------------------------------------------------------------------- |
| `--real`  | Run the service and API tests against PostgreSQL with `SqlAlchemyUnitOfWork`.          |
| `--clean` | With `--real`, delete all rows (keeping the tables) after the run.                     |

```bash
uv run pytest tests/services tests/entrypoints --real           # data is kept
uv run pytest tests/services tests/entrypoints --real --clean   # data is deleted at the end
```

`--clean` empties every table in the database `DATABASE_URL` points to, not
just the test data. Only use it on a local development database.

Other useful commands:

```bash
uv run pytest -v                  # show each test name and result
uv run pytest tests/domain        # one folder
uv run pytest -k sign_in          # tests whose name contains "sign_in"
uv run pytest -x                  # stop at the first failure
```

Test layout:

| Folder              | What it tests                                              |
| ------------------- | ---------------------------------------------------------- |
| `tests/domain`      | Domain entities and their rules (pure Python)              |
| `tests/services`    | Command handlers, event handlers and the message bus       |
| `tests/entrypoints` | The FastAPI app                                            |
| `tests/infra`       | The SQLAlchemy unit of work against PostgreSQL             |

## Running the API

```bash
uv run uvicorn manger.entrypoints.fastapi_app:create_app --factory
```

The API listens on `http://127.0.0.1:8000`. Add `--port 9000` to change the
port, or `--reload` to restart on code changes.

Interactive docs, where you can try every endpoint, are at
`http://127.0.0.1:8000/docs`.

### Endpoints

| Method and path                           | Body                                          | Success                 |
| ----------------------------------------- | --------------------------------------------- | ----------------------- |
| `POST /sign_up`                           | `name`, `username`, `password`                | `201 {"user_id": ...}`  |
| `POST /sign_in`                           | `username`, `password`                        | `200 {"user_id": ...}`  |
| `POST /users/{user_id}/books`             | multipart `file`, `storage_provider`, optional `name` | `201 {"book_id": ...}` |
| `GET /users/{user_id}`                    | none                                          | `200` user and `books`  |
| `DELETE /users/{user_id}/books/{book_id}` | none                                          | `204`                   |

`storage_provider` is `"s3"` or `"local"`.

`POST /users/{user_id}/books` accepts a PDF or Word file (`.pdf`, `.doc`,
`.docx`) and a `storage_provider` of `"local"` or `"s3"`. Adding the book
raises two events: one stores the file, and one asks for it to be parsed.
`"local"` writes the file under the directory in `LOCAL_STORAGE_PATH` in
`services/app/.env` (relative paths start from `services/app`). The book's
`storage_key` is the path relative to that directory. `"s3"` is not
implemented and returns 404. If `name` is omitted, the book is named from
the file name.

The parse event is published to the RabbitMQ queue `parse_book`. Start the
broker and the worker from [services/parsing](../parsing/README.md). The
worker renders the book to page images and sends them to PaddleOCR.

`GET /users/{user_id}` returns `user_id`, `name`, `username`, and `books`.
Each book has `book_id`, `name`, `storage_provider`, and `storage_key`.
The password hash is not included.

Errors return `{"detail": ...}` with one of these status codes:

| Status | When                                                                          |
| ------ | ----------------------------------------------------------------------------- |
| 400    | The domain rejects a value, e.g. a blank name or password                     |
| 401    | Wrong username or password                                                    |
| 404    | Unknown user or book, or S3 storage (not implemented)                         |
| 409    | Username already taken                                                        |
| 415    | Upload is not a PDF or Word file                                              |
| 422    | Malformed request: missing field, body not JSON, unknown provider, bad UUID   |

### Example

```bash
curl -X POST http://127.0.0.1:8000/sign_up \
  -H "Content-Type: application/json" \
  -d '{"name": "Ahmed", "username": "ahmed", "password": "secret"}'
# {"user_id": "1d51f8fa-..."}

curl -X POST http://127.0.0.1:8000/sign_in \
  -H "Content-Type: application/json" \
  -d '{"username": "ahmed", "password": "secret"}'

curl -X POST http://127.0.0.1:8000/users/<user_id>/books \
  -F "storage_provider=local" \
  -F "name=Clean Architecture" \
  -F "file=@clean-arch.pdf"
# {"book_id": "d8cea35d-..."}

curl -X DELETE http://127.0.0.1:8000/users/<user_id>/books/<book_id>

curl http://127.0.0.1:8000/users/<user_id>
```

The same in PowerShell:

```powershell
$base = "http://127.0.0.1:8000"
$user = Invoke-RestMethod -Method Post "$base/sign_up" -ContentType application/json `
  -Body '{"name": "Ahmed", "username": "ahmed", "password": "secret"}'
$book = Invoke-RestMethod -Method Post "$base/users/$($user.user_id)/books" `
  -Form @{ storage_provider = "local"; name = "Clean Architecture"; file = Get-Item .\clean-arch.pdf }
Invoke-WebRequest -Method Delete "$base/users/$($user.user_id)/books/$($book.book_id)"
Invoke-RestMethod "$base/users/$($user.user_id)"
```

Removing a book logs a line from the domain's events, for example
`Book <id> removed from user <id>`.

The API has no authentication yet: the book endpoints trust the `user_id` in
the URL. Don't expose it outside local development.
