# backend/app/init_data.py
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .config import settings  # DATA_DIR="Datos" en .env por defecto :contentReference[oaicite:3]{index=3}

def ensure_data_tree() -> None:
    """
    Crea el árbol base en 'Datos' y migra datos legados si los hubiese:
      - data/ajustes/dominios.json  -> Datos/dominios.json
      - data/users/**/*             -> Datos/usuarios/**/*  (profile.json -> perfil.json)
    """
    base = Path(settings.data_dir)
    subdirs = [
        ".locks",
        "ajustes",
        "usuarios",
        "solicitudes",
        "asistencia",
        "votaciones",
        "logs",
        "backups",
        "_quarantine",
    ]
    for s in subdirs:
        (base / s).mkdir(parents=True, exist_ok=True)

    _migrate_legacy_data(base)


def _migrate_legacy_data(base: Path) -> None:
    """
    Migra estructuras antiguas para unificar todo bajo 'Datos'.
    Operaciones idempotentes (si ya está migrado, no hace nada).
    """

    # 1) Mover dominios: data/ajustes/dominios.json  -> Datos/dominios.json
    #    y también desde la ruta antigua dentro de Datos/ajustes a Datos/ (si existiera).
    proyecto_root = Path(".").resolve()

    legacy_data_root = proyecto_root / "data"
    legacy_domains = legacy_data_root / "ajustes" / "dominios.json"
    new_domains = base / "dominios.json"
    old_domains_inside_datos = base / "ajustes" / "dominios.json"

    try:
        if legacy_domains.exists() and not new_domains.exists():
            new_domains.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_domains), str(new_domains))
    except Exception:
        # no romper arranque por una migración
        pass

    try:
        if old_domains_inside_datos.exists() and not new_domains.exists():
            new_domains.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_domains_inside_datos), str(new_domains))
    except Exception:
        pass

    # 2) Mover usuarios: data/users -> Datos/usuarios
    legacy_users_dir = legacy_data_root / "users"
    new_users_dir = base / "usuarios"

    if legacy_users_dir.exists():
        new_users_dir.mkdir(parents=True, exist_ok=True)

        # mover index.json si existe
        legacy_index = legacy_users_dir / "index.json"
        if legacy_index.exists() and not (new_users_dir / "index.json").exists():
            try:
                shutil.move(str(legacy_index), str(new_users_dir / "index.json"))
            except Exception:
                pass

        # mover cada carpeta de usuario y renombrar profile.json -> perfil.json
        for item in legacy_users_dir.iterdir():
            if item.is_dir():
                destino = new_users_dir / item.name
                destino.mkdir(parents=True, exist_ok=True)
                # Mover todo dentro
                for sub in item.iterdir():
                    try:
                        if sub.name == "profile.json":  # legacy
                            shutil.move(str(sub), str(destino / "perfil.json"))
                        else:
                            shutil.move(str(sub), str(destino / sub.name))
                    except Exception:
                        pass
        # Opcional: intentar borrar el árbol legacy vacío
        try:
            # si quedó algo, no pasa nada
            shutil.rmtree(legacy_users_dir, ignore_errors=True)
        except Exception:
            pass
