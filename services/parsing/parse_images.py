"""Send page images to the PaddleOCR vLLM endpoint and save each response.

Up to `OCR_CONCURRENCY` images (10 by default) are in flight at once.
asyncio schedules the calls and a thread pool runs the blocking PaddleOCR client.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import dotenv_values

_ENV_FILE = Path(__file__).resolve().parent / ".env"
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_thread_state = threading.local()
_pipeline_lock = threading.Lock()
logger = logging.getLogger(__name__)

Predict = Callable[[Path], list]


def parse_images(
    images_dir: Path,
    book_path: Path,
    book_name: str,
    *,
    concurrency: int | None = None,
    predict: Predict | None = None,
) -> Path:
    """Parse every image in `images_dir` and return the `{book_name}_parsed` directory."""
    images_dir = Path(images_dir)
    images = sorted(
        path for path in images_dir.iterdir() if path.suffix.lower() in _IMAGE_SUFFIXES
    )
    if not images:
        raise FileNotFoundError(f"No page images in {images_dir}")

    parsed_dir = Path(book_path).parent / _folder_name(book_name, "parsed")
    parsed_dir.mkdir(parents=True, exist_ok=True)
    workers = concurrency if concurrency is not None else _concurrency()
    runner = predict or _predict_with_paddleocr
    asyncio.run(_parse_all(images, parsed_dir, workers, runner))
    return parsed_dir


def openai_base_url(raw: str | None = None) -> str:
    """OpenAI base URL for the vLLM server. A missing `/v1` is added."""
    value = (raw if raw is not None else _setting("VLLM_OPENAI_ENDPOINT")).strip().rstrip("/")
    if not value:
        raise RuntimeError("VLLM_OPENAI_ENDPOINT is missing from services/parsing/.env")
    if not value.endswith("/v1"):
        value = value + "/v1"
    return value


async def _parse_all(
    images: list[Path], parsed_dir: Path, concurrency: int, predict: Predict
) -> None:
    executor = ThreadPoolExecutor(max_workers=concurrency)
    semaphore = asyncio.Semaphore(concurrency)
    loop = asyncio.get_running_loop()

    async def one(image: Path) -> None:
        async with semaphore:
            pages = await loop.run_in_executor(executor, predict, image)
        _write_json(parsed_dir / f"{image.stem}.json", image.name, pages)

    try:
        await asyncio.gather(*(one(image) for image in images))
    finally:
        executor.shutdown(wait=True)


def _predict_with_paddleocr(image: Path) -> list:
    from paddleocr import PaddleOCRVL

    pipeline = getattr(_thread_state, "pipeline", None)
    if pipeline is None:
        kwargs = {
            "vl_rec_backend": "vllm-server",
            "vl_rec_server_url": openai_base_url(),
            "vl_rec_max_concurrency": 1,
            "use_layout_detection": True,
            "use_chart_recognition": True,
            "format_block_content": True,
            # One image at a time inside the library. Its queue workers race
            # the shared HTTP loop when several pages start together, and the
            # page result is then never returned.
            "use_queues": False,
        }
        model_name = _setting("VLLM_MODEL_NAME")
        api_key = _setting("VLLM_API_KEY")
        if model_name:
            kwargs["vl_rec_api_model_name"] = model_name
        if api_key:
            kwargs["vl_rec_api_key"] = api_key
        # The client starts one process-wide HTTP loop. Two threads must not
        # do that at the same time, or each page waits on a future that never
        # completes and no JSON file is written.
        with _pipeline_lock:
            pipeline = PaddleOCRVL(**kwargs)
        _thread_state.pipeline = pipeline

    pages = []
    for result in pipeline.predict(str(image)):
        raw = result.json() if callable(getattr(result, "json", None)) else result.json
        pages.append(_to_jsonable(raw))
    return pages


def _write_json(path: Path, image_name: str, pages: list) -> None:
    payload = {"image": image_name, "result": pages}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info("saved %s", path)


def _to_jsonable(value):
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "tolist"):
        return _to_jsonable(value.tolist())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _folder_name(book_name: str, suffix: str) -> str:
    invalid = '<>:"/\\|?*'
    cleaned = "".join(
        "_" if character in invalid or ord(character) < 32 else character
        for character in book_name
    ).strip().rstrip(".")
    if not cleaned:
        cleaned = "book"
    return f"{cleaned}_{suffix}"


def _concurrency() -> int:
    raw = _setting("OCR_CONCURRENCY") or "10"
    value = int(raw)
    if value < 1:
        raise RuntimeError("OCR_CONCURRENCY must be at least 1")
    return value


def _setting(key: str) -> str:
    configured = os.environ.get(key, "").strip()
    if configured:
        return configured
    if _ENV_FILE.is_file():
        return (dotenv_values(_ENV_FILE).get(key) or "").strip()
    return ""
