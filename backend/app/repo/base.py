from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import orjson
from filelock import FileLock

from ..config import settings  # <- SIEMPRE desde config global

# Carpeta raiz de datos (unificada)
DATA_DIR = Path(settings.data_dir)

def ensure_dir(path: Path | str) -> None:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)

# ---------- JSON helpers (atómicos) ----------
def _write_atomic(dst: Path, content: bytes) -> None:
    ensure_dir(dst.parent)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(dst)

def read_json(path: Path | str, default: Any = None) -> Any:
    p = Path(path)
    try:
        data = p.read_bytes()
    except FileNotFoundError:
        return default
    return orjson.loads(data)

def write_json(path: Path | str, data: Any) -> None:
    p = Path(path)
    payload = orjson.dumps(data)
    # lock por fichero dentro de Datos/.locks
    lock_file = DATA_DIR / ".locks" / (p.name + ".lock")
    ensure_dir(lock_file.parent)
    with FileLock(str(lock_file)):
        _write_atomic(p, payload)

# ---------- JSONL helpers ----------
def append_jsonl(path: Path | str, record: Any) -> None:
    p = Path(path)
    line = orjson.dumps(record) + b"\n"
    lock_file = DATA_DIR / ".locks" / (p.name + ".lock")
    ensure_dir(p.parent)
    ensure_dir(lock_file.parent)
    with FileLock(str(lock_file)):
        with p.open("ab") as fh:
            fh.write(line)

def read_jsonl(path: Path | str) -> Iterator[Any]:
    p = Path(path)
    if not p.exists():
        return iter(())
    with p.open("rb") as fh:
        for line in fh:
            if not line.strip():
                continue
            yield orjson.loads(line)
