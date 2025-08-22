# Panel de Votaciones y Asistencia — Fase 0 (Fundaciones)

Backend en **Python (FastAPI)** con persistencia en disco (`Datos/`), preparado para
enviar emails vía **Gmail con clave de aplicación**.

## Puesta en marcha (local)

1) Requisitos: Python 3.11+  
2) Crear entorno e instalar dependencias:
```bash
python -m venv .venv
source .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
3) Configura variables: copia `.env.example` a `.env` y edita valores (SMTP incluido).  
4) Arranca:
```bash
uvicorn backend.app.main:app --reload
```
Accede a: http://localhost:8000/docs

## Gmail con clave de aplicación
- Activa la autenticación en dos pasos (2FA) en tu cuenta de Google.
- Genera una “Clave de aplicación” (App Password) y úsala como `SMTP_PASSWORD`.
- Host: `smtp.gmail.com`, Port: `587`, TLS: STARTTLS.

## Docker
```bash
docker compose up --build -d
```

## Estructura
- `backend/` — código FastAPI y utilidades
- `Datos/` — almacenamiento primario (se crea solo al iniciar)
- Endpoint de salud: `GET /health`
- Endpoint de prueba SMTP (modo DEV): `POST /_dev/test-email`

> Esta base está alineada con el roadmap (persistencia en `Datos/`, Pydantic, orjson, file locks, TZ Europe/Madrid) y lista para expandir Fase 1 (login por OTP).
