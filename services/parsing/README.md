# parsing

Turns an uploaded book into page images, then sends those images to PaddleOCR.
Run every command from this directory (`services/parsing`).

## 1. Install

```bash
uv sync
```

Word files (`.doc`, `.docx`) also need LibreOffice, with `soffice` on `PATH`.

## 2. Check `.env`

```
VLLM_OPENAI_ENDPOINT=http://127.0.0.1:8092/
VLLM_MODEL_NAME=PaddleOCR-VL-1.6-0.9B
OCR_CONCURRENCY=10
LOCAL_STORAGE_PATH=../app/storage
RABBITMQ_URL=amqp://pdf_reader:pdf_reader@localhost:5672/
```

`LOCAL_STORAGE_PATH` is where `services/app` saves uploaded books. A relative
path starts from this directory. A missing `/v1` on the endpoint is added
automatically.

## 3. Start RabbitMQ and vLLM

```bash
docker compose up -d
```

| Service | Address |
| --- | --- |
| RabbitMQ | `localhost:5672` (user `pdf_reader`, password `pdf_reader`) |
| RabbitMQ management | `http://localhost:15672` |
| PaddleOCR vLLM | `http://localhost:8092/v1` |

vLLM needs an NVIDIA GPU. The first start downloads
`PaddlePaddle/PaddleOCR-VL-1.6` and can take several minutes. It is ready when
`http://localhost:8092/v1/models` lists `PaddleOCR-VL-1.6-0.9B`.

To start only one service:

```bash
docker compose up -d rabbitmq
docker compose up -d vllm
```

## 4. Start the worker

```bash
uv run python worker.py
```

It waits on the `parse_book` queue. When the app adds a book, the worker:

1. Renders each page to PNG in `{book name}_images`, next to the PDF.
2. Sends up to 10 images at a time to the vLLM endpoint.
3. Writes one JSON file per page in `{book name}_parsed`.

The JSON has the text, tables, charts, and box positions from PaddleOCR.
The first book also downloads the local layout model.

## 5. Try the sample book

```bash
uv run pytest tests/test_stored_book.py -q
```

That renders and parses
`services/app/storage/0350e5c2-01c8-4be5-a7aa-1d4957db0adc/833b5675-261d-4611-8847-2e8e88354352/document_2026_11_18_13_53_13.pdf`
and leaves the image and JSON folders beside it.

## Stop

```bash
docker compose down
```
