# backend/app/repo/exports.py
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..config import settings
from . import usuarios as usuarios_repo

DATA_DIR = Path(settings.data_dir)

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-_.]+", "", s)
    return s[:60] or "registro"

# ---------------- Usuarios ----------------
def export_usuarios_csv_to_file() -> str:
    """
    Guarda CSV de usuarios en Datos/usuarios/export_usuarios_YYYYMMDD.csv
    """
    csv_str = usuarios_repo.export_csv()  # ya existente
    today = datetime.now().strftime("%Y%m%d")
    out_dir = DATA_DIR / "usuarios"
    _ensure_dir(out_dir)
    out_path = out_dir / f"export_usuarios_{today}.csv"
    out_path.write_text(csv_str, encoding="utf-8")
    return str(out_path)

# ---------------- Asistencia ----------------
def export_asistencia_csv(reunion_id: str) -> str:
    """
    Lee Datos/asistencia/{id}/reunion.json y asistentes.jsonl y genera:
    Datos/asistencia/{YYYY}/{MM}/asistencia_{id}_{slug}.csv

    Cabeceras (roadmap):
      ID, Título, Inicio(UTC y Europe/Madrid), Cierre(UTC y Europe/Madrid), Duración,
      NIU, Nombre, Email, Asistencia(Sí/No), Hora_de_union(Europe/Madrid)
    """
    base = DATA_DIR / "asistencia" / reunion_id
    meta_file = base / "reunion.json"
    asist_file = base / "asistentes.jsonl"

    if not meta_file.exists():
        raise FileNotFoundError(f"No existe {meta_file}")
    meta = json.loads(meta_file.read_text(encoding="utf-8") or "{}")
    titulo = str(meta.get("titulo") or meta.get("nombre") or f"reunion_{reunion_id}")
    inicio_utc = int(meta.get("inicio_ts", 0) or meta.get("inicio_utc_ts", 0))
    fin_utc = int(meta.get("fin_ts", 0) or meta.get("cierre_utc_ts", 0))
    # Duración
    dur_s = max(0, (fin_utc or 0) - (inicio_utc or 0))

    # Asistentes presentes (por user_id)
    presentes: Dict[str, int] = {}
    if asist_file.exists():
        with asist_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                uid = str(rec.get("user_id") or "")
                ts = int(rec.get("hora_union_utc") or rec.get("ts") or 0)
                if uid and ts and uid not in presentes:
                    presentes[uid] = ts

    # Listado de usuarios para marcar ausentes también
    usuarios = usuarios_repo.listar()  # devuelve lista de perfiles
    rows_io = io.StringIO()
    w = csv.writer(rows_io)
    w.writerow([
        "reunion_id", "titulo",
        "inicio_utc_iso", "inicio_eu_madrid",
        "fin_utc_iso", "fin_eu_madrid",
        "duracion_seg",
        "niu", "nombre", "email", "asistencia", "hora_union_eu_madrid",
    ])

    def iso_from_ts(ts: int, tz_name: str) -> str:
        try:
            from zoneinfo import ZoneInfo
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            if tz_name == "UTC":
                return dt.isoformat()
            return dt.astimezone(ZoneInfo(tz_name)).isoformat()
        except Exception:
            return ""

    for p in usuarios:
        uid = str(p.get("user_id") or "")
        niu = p.get("niu") or ""
        nombre = p.get("nombre") or ""
        email = p.get("email") or ""
        ts_union = presentes.get(uid)
        asistencia = "Sí" if ts_union else "No"
        w.writerow([
            reunion_id, titulo,
            iso_from_ts(inicio_utc, "UTC"),
            iso_from_ts(inicio_utc, "Europe/Madrid"),
            iso_from_ts(fin_utc, "UTC"),
            iso_from_ts(fin_utc, "Europe/Madrid"),
            str(dur_s),
            niu, nombre, email, asistencia,
            iso_from_ts(ts_union, "Europe/Madrid") if ts_union else "",
        ])

    # Ruta de salida
    now = datetime.now()
    out_dir = DATA_DIR / "asistencia" / f"{now:%Y}" / f"{now:%m}"
    _ensure_dir(out_dir)
    out_path = out_dir / f"asistencia_{reunion_id}_{_slug(titulo)}.csv"
    out_path.write_text(rows_io.getvalue(), encoding="utf-8")
    return str(out_path)

# ---------------- Votaciones ----------------
def export_votacion_csv(votacion_id: str) -> Dict[str, Optional[str]]:
    """
    Usa resultados ya calculados si existen:
      - resultados_agregados.json -> resultados_agregados.csv
      - resultados_nominales.csv si hay detalle y no es anónima

    Si no existen JSON de resultados, intenta derivar algo básico de votos.jsonl (opcional).
    Devuelve rutas generadas.
    """
    base = DATA_DIR / "votaciones" / votacion_id
    # Intenta leer metadatos para el slug
    titulo = "votacion"
    defin = base / "definicion_votacion.json"
    if defin.exists():
        try:
            d = json.loads(defin.read_text(encoding="utf-8") or "{}")
            titulo = d.get("titulo") or titulo
        except Exception:
            pass

    now = datetime.now()
    out_dir = DATA_DIR / "votaciones" / f"{now:%Y}" / f"{now:%m}" / f"{votacion_id}_{_slug(titulo)}"
    _ensure_dir(out_dir)

    agreg_json = base / "resultados_agregados.json"
    agreg_csv = out_dir / "resultados_agregados.csv"
    nominal_csv = out_dir / "resultados_nominales.csv"

    # Agregado
    if agreg_json.exists():
        try:
            data = json.loads(agreg_json.read_text(encoding="utf-8") or "{}")
            rows = io.StringIO()
            w = csv.writer(rows)
            w.writerow(["seccion", "valor", "conteo"])
            # opciones cerradas
            for op, cnt in (data.get("conteo") or {}).items():
                w.writerow(["opcion", op, int(cnt)])
            # abiertas
            for item in (data.get("abiertas") or []):
                w.writerow(["abierta", item.get("texto") or "", int(item.get("conteo") or 0)])
            agreg_csv.write_text(rows.getvalue(), encoding="utf-8")
        except Exception:
            pass  # ignora si el JSON está malformado

    # Nominal (si existe fuente previa)
    detalle_file = base / "resultados_nominales.csv"
    if detalle_file.exists():
        # ya había un CSV nominal generado por la capa de resultados → copiamos a carpeta de export
        nominal_csv.write_text(detalle_file.read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "agregado_csv": str(agreg_csv) if agreg_csv.exists() else None,
        "nominal_csv": str(nominal_csv) if nominal_csv.exists() else None,
    }
