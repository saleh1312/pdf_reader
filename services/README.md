# Services

Commands to run each service. Run them from the directory named in the heading.
Each Python service has its own virtual environment; `uv` creates it on `uv sync`.

Start the databases and RabbitMQ before the processes that use them.

| Service | Address |
| --- | --- |
| App Postgres | `localhost:5432`, database `pdf_reader` |
| App API | `http://127.0.0.1:8000` |
| RabbitMQ | `localhost:5672` (user `pdf_reader`, password `pdf_reader`) |
| PaddleOCR vLLM | `http://localhost:8092/v1` |
| Chatbot Postgres | `localhost:5433`, database `chatbot` |
| Chatbot API | `http://127.0.0.1:8001` |
| Frontend | `http://127.0.0.1:8080` |

## App

Directory: `services/app`

```powershell
uv sync
docker compose -f db/lunch/docker-compose.yml up -d
uv run uvicorn manger.entrypoints.fastapi_app:create_app --factory
```

Docs: `http://127.0.0.1:8000/docs`

Sign up, sign in, and upload a book. Uploading a book stores the file and publishes a parse request. More detail is in [app/README.md](app/README.md).

Stop the database:

```powershell
docker compose -f db/lunch/docker-compose.yml down
```

## Parsing

Directory: `services/parsing`

```powershell
uv sync
docker compose up -d
uv run python worker.py
```

`docker compose up -d` starts RabbitMQ and the PaddleOCR vLLM server. vLLM needs an NVIDIA GPU. The first start downloads the model and can take several minutes. It is ready when `http://localhost:8092/v1/models` lists `PaddleOCR-VL-1.6-0.9B`.

Leave `worker.py` running. It consumes the `parse_book` queue, writes page images and JSON next to the book, then sets `books.is_parsed` in the app database.

To start only the broker:

```powershell
docker compose up -d rabbitmq
```

Stop both containers:

```powershell
docker compose down
```

More detail is in [parsing/README.md](parsing/README.md).

## Chatbot

Directory: `services/chatbot`

```powershell
uv sync
docker compose up -d
uv run uvicorn manger.entrypoints.fastapi_app:create_app --factory --port 8001
```

The app database must already be running. Set `OPENAI_API_KEY`, `OPENAI_MODEL`, and `OPENAI_BASE_URL` in `services/chatbot/.env` before inferring. Leave `OPENAI_BASE_URL` empty for the official OpenAI API, or set a local server or `https://openrouter.ai/api/v1`.

Docs: `http://127.0.0.1:8001/docs`

| Method and path | Body | Success |
| --- | --- | --- |
| `POST /sessions` | `user_id`, `book_id` | `201 {"status": "success", "session_id": ...}` |
| `GET /users/{user_id}/sessions` | none | `200` list of `{session_id, book_id, preview}` |
| `GET /users/{user_id}/sessions/{session_id}` | none | `200` `{session_id, book_id, messages}` |
| `POST /infer` | `session_id`, `msg` | `200 {"message": ...}` |

`POST /sessions` reads the parsed pages of a book whose `is_parsed` flag is true and stores them as the session's system message. `POST /infer` sends that history plus `msg` to the model, stores the user message and the reply, and returns the reply.

Stop the chatbot database:

```powershell
docker compose down
```

## Frontend

Directory: `services/web`

React app, served by Vite. The app API and the chatbot API must already be running.

```powershell
npm install
npm run dev
```

Open `http://127.0.0.1:8080`. Sign up or log in at `/`. `/books` uploads a book and checks once a second whether it is parsed. When it is, **New session** opens `/chat`. That page lists this user's sessions on the left and shows the book's PDF on the right. Choosing a chat loads its history, and the box at the bottom continues that chat.

## Tests

From the service directory:

```powershell
uv run pytest
```
