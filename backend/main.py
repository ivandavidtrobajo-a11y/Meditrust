from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os
import logging
import uuid
import threading
import re
import json

from services.parser import parse_and_insert_consolidado
from services.prompt import build_prompt
from services.llm_service import LLMService
from database.datasets_db import save_dataset, get_latest_dataset, save_document_node, list_document_nodes, delete_document_node
from database.mongodb import get_db
from services.auth_service import (
    verify_password, create_access_token, decode_token,
    get_user_by_email, get_user_by_id, create_user, update_user,
    save_reset_token, get_reset_token, delete_reset_token, hash_password
)
from services.email_service import send_reset_email

import secrets
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

from fastapi import Response

@app.options("/{path:path}")
async def options_handler(path: str):
    """Maneja todas las solicitudes OPTIONS (preflight) para CORS."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*", # O tu dominio específico
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Credentials": "true",
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://medicconsult-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    automatic_options=False,
)

# Serve frontend static files in production (only if build exists)
#frontend_build = Path(__file__).resolve().parent.parent / "frontend" / "build"
#if frontend_build.exists():
    #from fastapi.staticfiles import StaticFiles
    #app.mount("/", StaticFiles(directory=str(frontend_build), html=True), name="frontend")
    #logging.info("Frontend static files mounted from %s", frontend_build)

security = HTTPBearer()

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

TASKS = {}

llm_service = LLMService()

# Seed admin user on startup
db = get_db()
if not db.users.find_one({"email": "admin@jsonapi.com"}):
    create_user("Carlo", "admin@jsonapi.com", "12345678", role="admin")
    logging.info("Admin user seeded: admin@jsonapi.com / 12345678")


class QuestionRequest(BaseModel):
    question: str
    model: str = None


# ── Auth models ─────────────────────────────────────

class AuthAttributes(BaseModel):
    email: str
    password: str = None
    name: str = None
    password_confirmation: str = None
    newPassword: str = None
    confirmPassword: str = None
    redirect_url: str = None
    token: str = None


class AuthData(BaseModel):
    type: str
    id: str = None
    attributes: AuthAttributes


class AuthRequest(BaseModel):
    data: AuthData


# ── Helpers ──────────────────────────────────────────

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    user = get_user_by_id(payload.get("id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


def _user_to_json(user) -> dict:
    return {
        "data": {
            "id": str(user["_id"]),
            "type": "users",
            "attributes": {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "profile_image": user.get("profile_image"),
                "createdAt": user.get("created_at"),
                "updateAt": user.get("updated_at"),
            },
            "links": {
                "self": f"/users/{user['_id']}"
            }
        }
    }


def extraer_mes_anio_del_nombre(filename: str):
    filename_lower = filename.lower()
    meses_map = {
        "enero": "Ene", "febrero": "Feb", "marzo": "Mar", "abril": "Abr",
        "mayo": "May", "junio": "Jun", "julio": "Jul", "agosto": "Ago",
        "septiembre": "Sep", "octubre": "Oct", "noviembre": "Nov", "diciembre": "Dic"
    }
    mes_detectado = "Consolidado"
    for mes_es, mes_abr in meses_map.items():
        if mes_es in filename_lower:
            mes_detectado = mes_abr
            break
    if mes_detectado == "Consolidado":
        numeros_mes = re.findall(r"\b\d{2}\b", filename)
        if numeros_mes:
            num = int(numeros_mes[0])
            if 1 <= num <= 12:
                listado = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
                mes_detectado = listado[num - 1]
    anio_match = re.search(r"20\d{2}", filename)
    anio_detectado = anio_match.group(0) if anio_match else "Actual"
    return mes_detectado, anio_detectado


# ── Auth endpoints ───────────────────────────────────

@app.post("/login")
def login(request: AuthRequest):
    attrs = request.data.attributes
    user = get_user_by_email(attrs.email)
    if not user or not verify_password(attrs.password, user["password"]):
        raise HTTPException(status_code=400, detail="Credenciales inválidas")

    access_token = create_access_token({
        "id": str(user["_id"]),
        "email": user["email"],
        "role": user.get("role", "embarazada"),
    })
    return {
        "token_type": "Bearer",
        "access_token": access_token,
        "refresh_token": access_token,
        "user": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user["email"],
            "role": user.get("role", "embarazada"),
        },
    }


@app.post("/register")
def register(request: AuthRequest):
    attrs = request.data.attributes
    existing = get_user_by_email(attrs.email)
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    user = create_user(attrs.name, attrs.email, attrs.password)
    access_token = create_access_token({
        "id": user["_id"],
        "email": user["email"],
        "role": user.get("role", "embarazada"),
    })
    return {
        "token_type": "Bearer",
        "access_token": access_token,
        "refresh_token": access_token,
        "user": {
            "id": user["_id"],
            "name": user.get("name", ""),
            "email": user["email"],
            "role": user.get("role", "embarazada"),
        },
    }


@app.post("/logout")
def logout():
    return None


@app.get("/me")
def get_profile(current_user=Depends(get_current_user)):
    return _user_to_json(current_user)


@app.patch("/me")
def patch_profile(request: AuthRequest, current_user=Depends(get_current_user)):
    attrs = request.data.attributes
    updates = {}
    if attrs.name:
        updates["name"] = attrs.name
    if attrs.email:
        updates["email"] = attrs.email
    if attrs.newPassword and attrs.newPassword == attrs.confirmPassword and len(attrs.newPassword) >= 8:
        updates["password"] = hash_password(attrs.newPassword)

    update_user(current_user["email"], updates)
    updated_user = get_user_by_email(updates.get("email", current_user["email"]))
    return _user_to_json(updated_user)


@app.post("/password-forgot")
def password_forgot(request: AuthRequest):
    attrs = request.data.attributes
    user = get_user_by_email(attrs.email)
    if not user:
        return None

    token = secrets.token_hex(20)
    save_reset_token(attrs.email, token)

    redirect_url = attrs.redirect_url or f"{os.getenv('APP_URL_CLIENT', 'http://localhost:3000')}/auth/reset-password"
    reset_link = f"{redirect_url}?token={token}&email={attrs.email}"
    send_reset_email(attrs.email, reset_link)

    return None


@app.post("/password-reset")
def password_reset(request: AuthRequest):
    attrs = request.data.attributes
    found = get_reset_token(attrs.email, attrs.token)
    if not found:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

    if len(attrs.password) < 8 or attrs.password != attrs.password_confirmation:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres y coincidir")

    update_user(attrs.email, {"password": hash_password(attrs.password)})
    delete_reset_token(attrs.email)
    return None


# ── Medical endpoints ────────────────────────────────

@app.get("/")
def root():
    return {"status": "API funcionando"}


@app.get("/models")
def list_models():
    return llm_service.get_available_models()


@app.post("/ask/")
async def ask_question(request: QuestionRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Pregunta vacía")

    model = request.model or llm_service.get_default_model()

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "pending", "answer": None, "error": None}

    thread = threading.Thread(
        target=_process_question_task,
        args=(task_id, question, model),
        daemon=True
    )
    thread.start()

    return {"task_id": task_id}


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return {"status": "not_found"}
    return {
        "status": task["status"],
        "answer": task.get("answer"),
        "error": task.get("error")
    }


@app.post("/cancel/{task_id}")
async def cancel_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return {"status": "not_found", "message": "La tarea no existe o ya finalizó"}
    if task["status"] == "running" or task["status"] == "pending":
        task["status"] = "cancelled"
        task["answer"] = "Consulta cancelada por el usuario."
        return {"status": "cancelled", "message": "Tarea cancelada correctamente"}
    return {"status": task["status"], "message": "La tarea ya ha finalizado"}


@app.get("/documents")
async def list_docs():
    docs = list_document_nodes()
    return {"documentos": docs}


@app.delete("/documents/{id}")
async def delete_doc(id: str):
    try:
        deleted = delete_document_node(id)
        if not deleted:
            return {"message": f"Documento con ID {id} no encontrado"}
        return {"message": f"Documento con ID {id} eliminado correctamente"}
    except Exception as e:
        logging.exception(f"Error al eliminar documento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        save_document_node(file.filename, file_path, contenido="")

        parse_mensaje = ""
        try:
            parse_success = parse_and_insert_consolidado(file_path, documento_nombre=file.filename)
            if parse_success:
                logging.info(f"Archivo {file.filename} parseado e insertado en MongoDB")

                ds = get_latest_dataset()
                if ds and ds.get("conceptos"):
                    contexto = _generar_contexto(ds, file.filename)
                    db.datasets.update_one({"_id": ds["_id"]}, {"$set": {"contexto": contexto}})
                    logging.info(f"Contexto generado para {file.filename}")

                parse_mensaje = " Datos importados correctamente."
            else:
                parse_mensaje = " El archivo se guardó pero no se pudo parsear la estructura."
        except Exception as e:
            logging.warning(f"No se pudo parsear/insertar estructura: {e}")
            parse_mensaje = f" El archivo se guardó pero hubo un error al parsear: {e}"

        return {"filename": file.filename, "message": f"Archivo subido correctamente.{parse_mensaje}"}

    except Exception as e:
        logging.exception(f"Error al subir archivo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generar_contexto(ds: dict, filename: str) -> str:
    mes, anio = extraer_mes_anio_del_nombre(filename)
    lines = []
    lines.append("--- RESUMEN DE DATOS MÉDICOS ---")
    lines.append(f"Archivo: {filename}")
    lines.append(f"Mes: {mes} | Año: {anio}")
    lines.append(f"Policlínico: {ds.get('policlinico', 'S/D')}")
    cmfs = ds.get("cmfs", [])
    lines.append(f"CMFs disponibles: {', '.join(cmfs)}")
    lines.append("")

    conceptos = ds.get("conceptos", [])
    lines.append("Conceptos y sus totales generales:")
    for c in conceptos:
        lines.append(f"- {c['nombre']}: Total General = {c.get('total_general', 'N/A')}")

    lines.append("")
    lines.append("Datos detallados por CMF y Concepto:")
    for c in conceptos:
        lines.append(f"\n  {c['nombre']}:")
        registros = c.get("registros", {})
        for cmf, valor in registros.items():
            lines.append(f"    {cmf}: {valor}")

    lines.append("")
    lines.append("--- FIN DEL CONTEXTO ---")
    return "\n".join(lines)


# ── Dashboard ────────────────────────────────────────

@app.get("/dashboard")
def dashboard_data():
    ds = get_latest_dataset()
    if not ds:
        return {"error": "No hay datos cargados"}

    filename = ds.get("filename", "")
    mes_actual, anio_actual = extraer_mes_anio_del_nombre(filename)

    CONCEPTOS_DASHBOARD = [
        "SÍNDROME FEBRIL", "RIESGO PRECONCEPCIONAL", "MUJER EDAD FERTIL",
        "CONSULTA MEDICINA", "ALTA INGRESO  HOGAR", "INGRESO HOGAR",
    ]

    dashboard = {}
    conceptos = ds.get("conceptos", [])
    for c in conceptos:
        if c["nombre"] in CONCEPTOS_DASHBOARD:
            total = sum(v for v in c.get("registros", {}).values() if isinstance(v, (int, float)))
            dashboard[c["nombre"]] = [{
                "mes": mes_actual,
                "anio": anio_actual,
                "valor": total,
            }]

    dashboard["CMF"] = [{
        "mes": "Total",
        "anio": "Activos",
        "valor": len(ds.get("cmfs", [])),
    }]

    return dashboard


# ── LLM question processing ──────────────────────────

def _process_question_task(task_id: str, question: str, model: str = None):
    TASKS[task_id]["status"] = "running"
    try:
        ds = get_latest_dataset()
        contexto = ds.get("contexto", "") if ds else "No hay datos cargados en la base de datos."

        prompt_text = build_prompt(question, contexto=contexto)
        effective_model = model or llm_service.get_default_model()

        respuesta = llm_service.chat(
            effective_model,
            messages=[{"role": "user", "content": prompt_text}]
        )

        answer_text = respuesta.get("message", {}).get("content", str(respuesta))

        TASKS[task_id]["status"] = "finished"
        TASKS[task_id]["answer"] = answer_text

    except Exception as e:
        logging.exception(f"Error procesando pregunta {task_id}: {e}")
        TASKS[task_id]["status"] = "error"
        TASKS[task_id]["error"] = str(e)
