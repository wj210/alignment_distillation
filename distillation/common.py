"""Small JSONL and run-metadata helpers shared by filtering and generation."""

import hashlib
import json
from itertools import islice
from pathlib import Path


def digest(data: str | bytes) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def append_jsonl(handle, row: dict) -> None:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    handle.flush()


def batches(rows, size: int):
    rows = iter(rows)
    while batch := list(islice(rows, size)):
        yield batch


def prepare_run(directory: Path, metadata: dict) -> None:
    """Refuse to mix different inputs/models/settings into a resumed run."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "config.json"
    metadata = json.loads(json.dumps(metadata, default=str))
    if path.exists():
        if json.loads(path.read_text()) != metadata:
            raise ValueError(f"Run settings changed; use a new output directory: {directory}")
    else:
        if any(directory.iterdir()):
            raise ValueError(f"Output directory has files but no config.json: {directory}")
        with path.open("x") as handle:
            json.dump(metadata, handle, indent=2)


def write_once(path: Path, rows: list[dict]) -> None:
    if path.exists():
        if read_jsonl(path) != rows:
            raise ValueError(f"Refusing to overwrite different data: {path}")
        return
    with path.open("x") as handle:
        for row in rows:
            append_jsonl(handle, row)
