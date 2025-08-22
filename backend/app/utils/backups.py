# backend/app/utils/backups.py
from __future__ import annotations

import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    # Opcional (si está instalado)
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    import zoneinfo
except Exception:  # pragma: no cover
    AsyncIOScheduler = None  # type: ignore
    zoneinfo = None  # type: ignore

from ..config import settings

DATA_DIR = Path(settings.data_dir)
BACKUPS_DIR = DATA_DIR / "backups"
EXCLUDE_DIRS = {"backups"}  # evita anidar backups dentro del zip


def create_backup_zip(prefix: Optional[str] = None) -> str:
    """
    Crea un zip con el contenido de Datos/ (excluyendo Datos/backups/).
    Devuelve la ruta del zip creado.
    """
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    base_name = f"{prefix + '_' if prefix else ''}backup_{date_str}"
    zip_path = BACKUPS_DIR / f"{base_name}.zip"

    # Si existe, agrega sufijo incremental
    i = 2
    while zip_path.exists():
        zip_path = BACKUPS_DIR / f"{base_name}_{i}.zip"
        i += 1

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in DATA_DIR.rglob("*"):
            if p.is_dir():
                # saltar carpetas excluidas
                rel_parts = p.relative_to(DATA_DIR).parts
                if rel_parts and rel_parts[0] in EXCLUDE_DIRS:
                    continue
                continue
            rel = p.relative_to(DATA_DIR)
            # excluir archivos dentro de carpetas excluidas
            if rel.parts and rel.parts[0] in EXCLUDE_DIRS:
                continue
            zf.write(p, arcname=str(rel))
    return str(zip_path)


# --- Programación diaria (opcional con APScheduler) ---
_scheduler = None

def start_scheduler() -> None:
    """
    Programa backup diario a las 03:30 Europe/Madrid si APScheduler está disponible.
    Si no lo está, no hace nada (no rompe).
    """
    global _scheduler
    if AsyncIOScheduler is None or zoneinfo is None:
        return
    if _scheduler:
        return
    tz = zoneinfo.ZoneInfo("Europe/Madrid")
    _scheduler = AsyncIOScheduler(timezone=tz)
    _scheduler.add_job(create_backup_zip, "cron", hour=3, minute=30, id="daily_backup")
    _scheduler.start()
