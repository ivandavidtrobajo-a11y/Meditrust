from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os
import logging
import uuid
import threading
import re
import unicodedata
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
from datetime import datetime, timezone
from io import BytesIO
from gridfs import GridFSBucket
from bson import ObjectId
from bson.errors import InvalidId
from PIL import Image, UnidentifiedImageError
from dotenv import load_dotenv
from database.neo4j_schema import create_constraints
from services.neo4j_selector import select_medical_data
from services.authorization import require_role, require_admin, require_patient_access, require_active_user
from services.clinical_workflow import router as clinical_workflow_router
from services.capture_analysis import manager as capture_analysis_manager

load_dotenv()
try:
    create_constraints()
    logging.info("Esquema de Neo4j inicializado correctamente")
except Exception as e:
    logging.error(f"Error inicializando Neo4j: {e}")

app = FastAPI()

security = HTTPBearer()


cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://memedicconsult-frontend.onrender.com",
]
cors_origins.extend(
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(cors_origins)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

TASKS = {}

llm_service = LLMService()

# Optional admin bootstrap. Never commit default credentials.
db = get_db()
try:
    db["chat_preferences"].create_index(
        [("user_id", 1), ("conversation_id", 1)],
        unique=True,
        name="unique_user_conversation_model",
    )
except Exception:
    logging.exception("No se pudo crear el índice de preferencias del chat")

bootstrap_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip()
bootstrap_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
if bootstrap_email and bootstrap_password and not db.users.find_one({"email": bootstrap_email}):
    create_user(
        os.getenv("BOOTSTRAP_ADMIN_NAME", "Administrador"),
        bootstrap_email,
        bootstrap_password,
        role="admin",
    )
    logging.info("Bootstrap administrator created from environment configuration.")




@app.on_event("startup")
def start_capture_analysis_worker():
    try:
        database = get_db()
        indexes = [
            (database.capture_analysis_jobs, [("status", 1), ("next_attempt_at", 1), ("created_at", 1)]),
            (database.capture_analysis_jobs, [("patient_id", 1), ("gridfs_id", 1)]),
            (database.capture_analysis_runs, [("patient_id", 1), ("gridfs_id", 1), ("started_at", -1)]),
            (database.capture_analysis_reviews, [("patient_id", 1), ("gridfs_id", 1), ("reviewed_at", -1)]),
        ]
        for collection, keys in indexes:
            try:
                collection.create_index(keys)
            except Exception:
                logging.exception("No se pudo crear un índice de análisis de capturas.")
    except Exception:
        logging.exception("MongoDB no está disponible al iniciar el trabajador; se reintentará desde el proceso.")
    capture_analysis_manager.start()


class QuestionRequest(BaseModel):
    question: str
    model: str = None
    conversation_id: str


class ChatPreferenceRequest(BaseModel):
    conversation_id: str
    model: str


class DoctorCreateRequest(BaseModel):
    name: str
    email: str
    password: str


class AdminUserUpdateRequest(BaseModel):
    name: str
    email: str


class AdminUserStatusRequest(BaseModel):
    is_active: bool


class CaptureReanalysisRequest(BaseModel):
    provider: str
    model: str


class CaptureReviewRequest(BaseModel):
    corrected_readings: dict
    note: str = ""


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
    require_active_user(user)
    return user


def _user_to_json(user) -> dict:
    return {
        "data": {
            "id": str(user["_id"]),
            "type": "users",
            "attributes": {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "role": user.get("role", "embarazada"),
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
    if user.get("is_active", True) is False:
        raise HTTPException(status_code=403, detail="Esta cuenta está desactivada. Contacta con un administrador.")

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


def _admin_user_payload(user: dict) -> dict:
    created_at = user.get("created_at")
    updated_at = user.get("updated_at")
    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "embarazada"),
        "is_active": user.get("is_active", True) is not False,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _audit_admin_user_action(actor: dict, action: str, target: dict, details: dict = None):
    try:
        get_db().audit_logs.insert_one({
            "actor_id": str(actor["_id"]),
            "action": action,
            "resource_type": "user",
            "resource_id": target["_id"],
            "details": details or {},
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        logging.exception("No se pudo registrar la auditoría de la operación administrativa.")


@app.get("/admin/users")
def admin_list_users(current_user=Depends(get_current_user)):
    """Lista cuentas sin exponer hashes ni credenciales; solo administradores."""
    require_admin(current_user)
    users = get_db().users.find({}, {"password": 0}).sort("created_at", -1)
    return {"users": [_admin_user_payload(user) for user in users]}


@app.get("/admin/users/{user_id}")
def admin_get_user(user_id: str, current_user=Depends(get_current_user)):
    """Devuelve los detalles de una cuenta, sin exponer credenciales."""
    require_admin(current_user)
    try:
        object_id = ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    user = get_db().users.find_one({"_id": object_id}, {"password": 0})
    if user is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    return {"user": _admin_user_payload(user)}


@app.patch("/admin/users/{user_id}")
def admin_update_user(
    user_id: str,
    request: AdminUserUpdateRequest,
    current_user=Depends(get_current_user),
):
    """Actualiza únicamente nombre y correo; el rol queda fuera de esta operación."""
    require_admin(current_user)
    try:
        object_id = ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    target = get_db().users.find_one({"_id": object_id})
    if target is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    name = request.name.strip()
    email = request.email.strip().lower()
    if len(name) < 2 or len(name) > 120:
        raise HTTPException(status_code=400, detail="El nombre debe tener entre 2 y 120 caracteres.")
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=400, detail="Introduce un correo electrónico válido.")

    duplicate = get_db().users.find_one({"email": email, "_id": {"$ne": object_id}})
    if duplicate:
        raise HTTPException(status_code=409, detail="Ya existe otra cuenta con ese correo.")

    get_db().users.update_one(
        {"_id": object_id},
        {"$set": {"name": name, "email": email, "updated_at": datetime.now(timezone.utc)}},
    )
    updated = get_db().users.find_one({"_id": object_id}, {"password": 0})
    _audit_admin_user_action(
        current_user, "user.updated", target,
        {"previous_email": target.get("email", ""), "new_email": email, "name": name},
    )
    return {"message": "Cuenta actualizada correctamente.", "user": _admin_user_payload(updated)}


@app.patch("/admin/users/{user_id}/status")
def admin_update_user_status(
    user_id: str,
    request: AdminUserStatusRequest,
    current_user=Depends(get_current_user),
):
    """Activa o desactiva una cuenta sin eliminar sus datos."""
    require_admin(current_user)
    try:
        object_id = ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    database = get_db()
    target = database.users.find_one({"_id": object_id})
    if target is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    if request.is_active is False:
        if object_id == current_user["_id"]:
            raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")
        if target.get("role", "embarazada") == "admin":
            active_admins = database.users.count_documents({
                "role": "admin",
                "is_active": {"$ne": False},
            })
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="No puedes desactivar al último administrador activo.")

    current_status = target.get("is_active", True) is not False
    if current_status == request.is_active:
        return {"message": "El estado de la cuenta ya estaba actualizado.", "user": _admin_user_payload(target)}

    database.users.update_one(
        {"_id": object_id},
        {"$set": {"is_active": request.is_active, "updated_at": datetime.now(timezone.utc)}},
    )
    updated = database.users.find_one({"_id": object_id}, {"password": 0})
    action = "user.reactivated" if request.is_active else "user.deactivated"
    _audit_admin_user_action(current_user, action, target, {
        "email": target.get("email", ""),
        "is_active": request.is_active,
    })
    message = "Cuenta reactivada correctamente." if request.is_active else "Cuenta desactivada correctamente."
    return {"message": message, "user": _admin_user_payload(updated)}


@app.post("/admin/doctors", status_code=201)
def admin_create_doctor(request: DoctorCreateRequest, current_user=Depends(get_current_user)):
    """Crea una cuenta médica; el rol nunca se acepta desde el cliente."""
    require_admin(current_user)
    name = request.name.strip()
    email = request.email.strip().lower()
    password = request.password
    if len(name) < 2 or len(name) > 120:
        raise HTTPException(status_code=400, detail="El nombre debe tener entre 2 y 120 caracteres.")
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=400, detail="Introduce un correo electrónico válido.")
    if len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=400, detail="La contraseña inicial debe tener entre 8 y 128 caracteres.")
    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.")
    doctor = create_user(name, email, password, role="medico")
    try:
        get_db().audit_logs.insert_one({
            "actor_id": str(current_user["_id"]),
            "action": "user.doctor_created",
            "resource_type": "user",
            "resource_id": doctor["_id"],
            "details": {"email": email, "role": "medico"},
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        logging.exception("No se pudo registrar la auditoría del alta médica.")
    return {
        "message": "Cuenta médica creada correctamente.",
        "user": {
            "id": doctor["_id"],
            "name": doctor.get("name", ""),
            "email": doctor["email"],
            "role": "medico",
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




@app.get("/health")
def health_check():
    """Comprobación básica del proceso API; no sustituye una prueba de conexión a cada servicio."""
    return {"status": "ok", "service": "meditrust-api"}


@app.post("/patient-captures/")
async def upload_patient_captures(
    patient_id: str = Form(...),
    patient_name: str = Form(""),
    notes: str = Form(""),
    files: list[UploadFile] = File(...),
    current_user=Depends(get_current_user),
):
    """Guarda imágenes de prueba en MongoDB GridFS y metadatos asociados al paciente."""
    patient_id = patient_id.strip()
    require_role(current_user, "embarazada")
    if patient_id != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="El identificador debe corresponder a tu propia cuenta.")
    patient_name = str(current_user.get("name", ""))[:120]
    notes = notes.strip()[:1000]

    if not patient_id or len(patient_id) > 100:
        raise HTTPException(status_code=400, detail="El identificador del paciente es obligatorio y debe tener como máximo 100 caracteres.")
    if not files or len(files) > 5:
        raise HTTPException(status_code=400, detail="Selecciona entre 1 y 5 imágenes por envío.")

    max_bytes = 8 * 1024 * 1024
    allowed_formats = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    validated = []

    # Validar todos los archivos antes de persistir ninguno.
    for upload in files:
        content = await upload.read(max_bytes + 1)
        if not content:
            raise HTTPException(status_code=400, detail="Uno de los archivos está vacío.")
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail="Cada imagen debe pesar como máximo 8 MB.")

        try:
            with Image.open(BytesIO(content)) as image:
                image_format = image.format
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise HTTPException(status_code=415, detail="Uno de los archivos no es una imagen válida.")

        if image_format not in allowed_formats:
            raise HTTPException(status_code=415, detail="Solo se aceptan imágenes JPEG, PNG o WEBP.")

        validated.append({
            "content": content,
            "filename": Path(upload.filename or "captura").name[:180],
            "content_type": allowed_formats[image_format],
            "size": len(content),
        })

    database = get_db()
    bucket = GridFSBucket(database, bucket_name="patient_capture_images")
    records = database["patient_capture_records"]
    uploaded_at = datetime.now(timezone.utc)
    user_id = str(current_user.get("_id", current_user.get("id", "")))
    stored = []

    try:
        for item in validated:
            storage_name = f"{uuid.uuid4().hex}_{item['filename']}"
            gridfs_id = bucket.upload_from_stream(
                storage_name,
                item["content"],
                metadata={
                    "patient_id": patient_id,
                    "original_filename": item["filename"],
                    "content_type": item["content_type"],
                    "uploaded_by": user_id,
                    "uploaded_at": uploaded_at,
                },
            )
            record = {
                "gridfs_id": str(gridfs_id),
                "patient_id": patient_id,
                "patient_name": patient_name,
                "original_filename": item["filename"],
                "content_type": item["content_type"],
                "size_bytes": item["size"],
                "notes": notes,
                "uploaded_by": user_id,
                "uploaded_at": uploaded_at,
            }
            records.insert_one(record)
            capture_analysis_manager.enqueue(patient_id, str(gridfs_id), item["filename"], actor_id=user_id)
            stored.append({
                "id": str(gridfs_id),
                "patient_id": patient_id,
                "filename": item["filename"],
                "content_type": item["content_type"],
                "size_bytes": item["size"],
                "analysis_status": "queued",
                "uploaded_at": uploaded_at.isoformat(),
            })
    except Exception:
        logging.exception("Error guardando capturas de paciente")
        raise HTTPException(status_code=500, detail="No se pudieron guardar todas las imágenes. Comprueba la conexión con MongoDB.")

    return {"message": f"{len(stored)} imagen(es) guardada(s) correctamente.", "captures": stored}


@app.get("/patient-captures/{patient_id}")
def list_patient_captures(patient_id: str, current_user=Depends(get_current_user)):
    """Lista capturas propias o de un paciente con asignación médica activa."""
    database = get_db()
    require_patient_access(current_user, patient_id, database)
    records = database["patient_capture_records"]
    captures = list(
        records.find(
            {"patient_id": patient_id},
            {"_id": 0, "gridfs_id": 1, "patient_id": 1, "patient_name": 1,
             "original_filename": 1, "content_type": 1, "size_bytes": 1,
             "notes": 1, "uploaded_at": 1, "analysis_status": 1,
             "analysis_updated_at": 1, "latest_run_id": 1},
        ).sort("uploaded_at", -1).limit(100)
    )
    for item in captures:
        if item.get("uploaded_at"):
            item["uploaded_at"] = item["uploaded_at"].isoformat()
        if item.get("analysis_updated_at"):
            item["analysis_updated_at"] = item["analysis_updated_at"].isoformat()
        latest = database["capture_analysis_runs"].find_one(
            {"patient_id": patient_id, "gridfs_id": item["gridfs_id"]},
            {"raw_response": 0, "model_content": 0},
            sort=[("started_at", -1)],
        )
        if latest:
            item["analysis"] = {
                "status": latest.get("classification", latest.get("status")),
                "readings": latest.get("readings", {}),
                "review_reasons": latest.get("review_reasons", []),
                "image_quality": latest.get("image_quality"),
                "started_at": latest.get("started_at").isoformat() if latest.get("started_at") else None,
            }
            latest_review = database["capture_analysis_reviews"].find_one(
                {"patient_id": patient_id, "gridfs_id": item["gridfs_id"]},
                sort=[("reviewed_at", -1)],
            )
            if latest_review:
                item["analysis"]["readings"] = latest_review.get("corrected_readings", item["analysis"]["readings"])
                item["analysis"]["reviewed"] = True
        else:
            item["analysis"] = None
    return {"patient_id": patient_id, "captures": captures}




def _capture_model_catalog():
    configured = os.getenv("CAPTURE_MODELS_JSON", "").strip()
    if configured:
        try:
            values = json.loads(configured)
            return [item for item in values if isinstance(item, dict)
                    and item.get("provider") in {"openrouter", "gemini", "huggingface"}
                    and item.get("id")]
        except ValueError:
            logging.exception("CAPTURE_MODELS_JSON no es válido.")
    models = []
    if os.getenv("OPENROUTER_API_KEY"):
        models.append({"id": os.getenv("OPENROUTER_DEFAULT_MODEL", "openrouter/free"),
                       "name": "OpenRouter (predeterminado)", "provider": "openrouter"})
    if os.getenv("GEMINI_API_KEY"):
        models.append({"id": os.getenv("GEMINI_DEFAULT_MODEL", "gemini-2.0-flash"),
                       "name": "Gemini", "provider": "gemini"})
    if os.getenv("HF_API_TOKEN"):
        models.append({"id": os.getenv("HF_DEFAULT_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct"),
                       "name": "Hugging Face", "provider": "huggingface"})
    return models


@app.get("/doctor/capture-models")
def doctor_capture_models(current_user=Depends(get_current_user)):
    require_role(current_user, "medico")
    return {"models": _capture_model_catalog()}


@app.post("/doctor/patient-captures/{patient_id}/{gridfs_id}/reanalyze", status_code=202)
def doctor_reanalyze_capture(patient_id: str, gridfs_id: str, request: CaptureReanalysisRequest,
                             current_user=Depends(get_current_user)):
    require_role(current_user, "medico")
    database = get_db()
    require_patient_access(current_user, patient_id, database)
    allowed = _capture_model_catalog()
    if not any(item.get("provider") == request.provider and item.get("id") == request.model for item in allowed):
        raise HTTPException(status_code=400, detail="El modelo no está configurado o permitido.")
    if database.patient_capture_records.find_one({"patient_id": patient_id, "gridfs_id": gridfs_id}) is None:
        raise HTTPException(status_code=404, detail="Captura no encontrada.")
    try:
        job_id = capture_analysis_manager.enqueue(
            patient_id, gridfs_id, "reanálisis", provider=request.provider,
            model=request.model, actor_id=str(current_user["_id"]), job_type="manual")
    except Exception as exc:
        raise HTTPException(status_code=404, detail="No se pudo crear el análisis: " + str(exc))
    return {"job_id": job_id, "status": "queued"}


@app.get("/patient-captures/{patient_id}/analysis-history")
def patient_capture_analysis_history(patient_id: str, gridfs_id: str = None,
                                      current_user=Depends(get_current_user)):
    database = get_db()
    require_patient_access(current_user, patient_id, database)
    include_raw = current_user.get("role") == "medico"
    return {
        "runs": capture_analysis_manager.history(patient_id, gridfs_id, include_raw=include_raw),
        "reviews": capture_analysis_manager.reviews(patient_id, gridfs_id),
    }


@app.put("/doctor/patient-captures/{patient_id}/{gridfs_id}/review")
def doctor_review_capture(patient_id: str, gridfs_id: str, request: CaptureReviewRequest,
                          current_user=Depends(get_current_user)):
    require_role(current_user, "medico")
    database = get_db()
    require_patient_access(current_user, patient_id, database)
    record = database.patient_capture_records.find_one({"patient_id": patient_id, "gridfs_id": gridfs_id})
    if record is None:
        raise HTTPException(status_code=404, detail="Captura no encontrada.")
    latest = database.capture_analysis_runs.find_one(
        {"patient_id": patient_id, "gridfs_id": gridfs_id}, sort=[("started_at", -1)])
    review = {
        "patient_id": patient_id, "gridfs_id": gridfs_id,
        "run_id": latest.get("_id") if latest else None,
        "original_readings": latest.get("readings", {}) if latest else {},
        "corrected_readings": request.corrected_readings,
        "note": request.note.strip()[:2000],
        "reviewed_by": str(current_user["_id"]),
        "reviewed_at": datetime.now(timezone.utc),
    }
    result = database.capture_analysis_reviews.insert_one(review)
    database.patient_capture_records.update_one(
        {"patient_id": patient_id, "gridfs_id": gridfs_id},
        {"$set": {"analysis_status": "reviewed", "latest_review_id": str(result.inserted_id)}})
    try:
        database.audit_logs.insert_one({
            "actor_id": str(current_user["_id"]), "action": "capture.reviewed",
            "resource_type": "patient_capture", "resource_id": gridfs_id,
            "details": {"patient_id": patient_id, "review_id": str(result.inserted_id)},
            "created_at": datetime.now(timezone.utc)})
    except Exception:
        logging.exception("No se pudo registrar la auditoría de revisión.")
    return {"review_id": str(result.inserted_id), "status": "reviewed"}


@app.get("/patient-captures/{patient_id}/{gridfs_id}/image")
def get_patient_capture_image(
    patient_id: str,
    gridfs_id: str,
    current_user=Depends(get_current_user),
):
    """Devuelve una imagen de GridFS solo si pertenece al usuario autenticado."""
    database = get_db()
    require_patient_access(current_user, patient_id, database)
    try:
        object_id = ObjectId(gridfs_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Captura no encontrada.")

    record = database["patient_capture_records"].find_one({
        "patient_id": patient_id,
        "gridfs_id": str(object_id),
    })
    if record is None:
        # No revelar si existe una captura perteneciente a otro usuario.
        raise HTTPException(status_code=404, detail="Captura no encontrada.")

    bucket = GridFSBucket(database, bucket_name="patient_capture_images")
    try:
        stream = bucket.open_download_stream(object_id)
    except Exception:
        logging.exception("No se pudo recuperar la imagen de GridFS")
        raise HTTPException(status_code=404, detail="Archivo de captura no encontrado.")

    filename = Path(record.get("original_filename") or "captura").name
    safe_filename = filename.replace('"', "").replace("\\", "_").replace("\r", "").replace("\n", "")
    def iter_gridfs_chunks():
        try:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            stream.close()

    return StreamingResponse(
        iter_gridfs_chunks(),
        media_type=record.get("content_type", "application/octet-stream"),
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/models")
def list_models(current_user=Depends(get_current_user)):
    require_role(current_user, "medico")
    return llm_service.get_available_models()


def _validate_conversation_id(conversation_id: str):
    value = (conversation_id or "").strip()
    if len(value) < 8 or len(value) > 128:
        raise HTTPException(status_code=400, detail="Identificador de conversación inválido")
    return value


@app.get("/chat/preferences/{conversation_id}")
def get_chat_preferences(
    conversation_id: str,
    current_user=Depends(get_current_user),
):
    require_role(current_user, "medico")
    conversation_id = _validate_conversation_id(conversation_id)
    user_id = str(current_user["_id"])
    preference = get_db()["chat_preferences"].find_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        {"_id": 0, "model": 1},
    )
    model = preference.get("model") if preference else None
    if model and not llm_service.is_model_available(model):
        model = None
    return {"conversation_id": conversation_id, "model": model}


@app.put("/chat/preferences")
def save_chat_preferences(
    request: ChatPreferenceRequest,
    current_user=Depends(get_current_user),
):
    require_role(current_user, "medico")
    conversation_id = _validate_conversation_id(request.conversation_id)
    model = (request.model or "").strip()
    if not llm_service.is_model_available(model):
        raise HTTPException(status_code=400, detail="El modelo seleccionado no está disponible o no está configurado")

    user_id = str(current_user["_id"])
    get_db()["chat_preferences"].update_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        {"$set": {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "model": model,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"saved": True, "conversation_id": conversation_id, "model": model}


@app.post("/ask/")
async def ask_question(
    request: QuestionRequest,
    current_user=Depends(get_current_user),
):
    require_role(current_user, "medico")
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Pregunta vacía")

    conversation_id = _validate_conversation_id(request.conversation_id)
    user_id = str(current_user["_id"])
    preferences = get_db()["chat_preferences"]
    preference = preferences.find_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        {"_id": 0, "model": 1},
    )
    model = request.model or (preference or {}).get("model") or llm_service.get_default_model()
    if not llm_service.is_model_available(model):
        raise HTTPException(status_code=400, detail="El modelo seleccionado no está disponible o no está configurado")

    preferences.update_one(
        {"user_id": user_id, "conversation_id": conversation_id},
        {"$set": {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "model": model,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "status": "pending",
        "answer": None,
        "error": None,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }

    thread = threading.Thread(
        target=_process_question_task,
        args=(task_id, question, model),
        daemon=True
    )
    thread.start()

    return {"task_id": task_id}


@app.get("/result/{task_id}")
async def get_result(task_id: str, current_user=Depends(get_current_user)):
    require_role(current_user, "medico")
    task = TASKS.get(task_id)
    if not task or task.get("user_id") != str(current_user["_id"]):
        return {"status": "not_found"}
    return {
        "status": task["status"],
        "answer": task.get("answer"),
        "error": task.get("error")
    }


@app.post("/cancel/{task_id}")
async def cancel_task(task_id: str, current_user=Depends(get_current_user)):
    require_role(current_user, "medico")
    task = TASKS.get(task_id)
    if not task or task.get("user_id") != str(current_user["_id"]):
        return {"status": "not_found", "message": "La tarea no existe o ya finalizó"}
    if task["status"] == "running" or task["status"] == "pending":
        task["status"] = "cancelled"
        task["answer"] = "Consulta cancelada por el usuario."
        return {"status": "cancelled", "message": "Tarea cancelada correctamente"}
    return {"status": task["status"], "message": "La tarea ya ha finalizado"}


@app.get("/documents")
async def list_docs(current_user=Depends(get_current_user)):
    require_role(current_user, "medico", "admin")
    docs = list_document_nodes()
    return {"documentos": docs}


@app.delete("/documents/{id}")
async def delete_doc(id: str, current_user=Depends(get_current_user)):
    require_role(current_user, "medico", "admin")
    try:
        deleted = delete_document_node(id)
        if not deleted:
            return {"message": f"Documento con ID {id} no encontrado"}
        return {"message": f"Documento con ID {id} eliminado correctamente"}
    except Exception as e:
        logging.exception(f"Error al eliminar documento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    require_role(current_user, "medico", "admin")
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

#_______neo4j_test______________________________________
@app.get("/neo4j-test")
def neo4j_test(question: str, current_user=Depends(get_current_user)):
    require_role(current_user, "medico")
    try:
        result = select_medical_data(question)

        return {
            "success": True,
            "question": question,
            "cmf": result.get("cmf"),
            "concepto": result.get("concepto"),
            "data": result.get("data", [])
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
# ── Dashboard ────────────────────────────────────────

@app.get("/dashboard")
def dashboard_data(current_user=Depends(get_current_user)):
    require_role(current_user, "medico", "admin")
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
#_____generar contexto de neo4j_____
def _generar_contexto_neo4j(resultado: dict, question: str) -> str:
    """
    Convierte los resultados obtenidos desde Neo4j
    en un contexto compacto para el LLM.
    """

    cmf = resultado.get("cmf")
    concepto = resultado.get("concepto")
    data = resultado.get("data", [])

    lines = []

    lines.append("--- DATOS MÉDICOS OBTENIDOS DESDE NEO4J ---")
    lines.append(f"Pregunta: {question}")

    if cmf:
        lines.append(f"CMF solicitado: {cmf}")

    if concepto:
        lines.append(f"Concepto solicitado: {concepto}")

    lines.append("")

    if not data:
        lines.append(
            "No se encontraron registros médicos en Neo4j "
            "que coincidan con la consulta."
        )
    else:
        lines.append(f"Registros encontrados: {len(data)}")
        lines.append("")

        for i, item in enumerate(data, start=1):
            lines.append(f"Registro {i}:")
            lines.append(f"  Policlínico: {item.get('policlinico', 'S/D')}")
            lines.append(f"  CMF: {item.get('cmf', 'S/D')}")
            lines.append(f"  Concepto: {item.get('concepto', 'S/D')}")
            lines.append(f"  Tipo: {item.get('tipo', 'S/D')}")
            lines.append(f"  Valor: {item.get('valor', 'S/D')}")
            lines.append("")

    lines.append(
        "IMPORTANTE: utiliza los datos proporcionados por Neo4j "
        "como fuente de información. No inventes valores que no "
        "aparezcan en los registros."
    )

    lines.append("--- FIN DE DATOS DE NEO4J ---")

    return "\n".join(lines)

def _is_simple_greeting(question: str) -> bool:
    """Identifica saludos aislados sin confundirlos con preguntas que los acompañan."""
    normalized = unicodedata.normalize("NFKD", (question or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())

    greetings = {
        "hola", "hola hola", "hey", "hi", "hello", "saludos",
        "buen dia", "buenos dias", "buenas tardes", "buenas noches",
        "que tal", "como estas", "como esta", "que hubo",
    }
    return normalized in greetings


# ── LLM question processing ──────────────────────────

def _process_question_task(task_id: str, question: str, model: str = None):
    TASKS[task_id]["status"] = "running"

    try:
        # Los saludos simples no necesitan consultar Neo4j ni construir
        # el contexto médico completo. Se envían al modelo seleccionado
        # como una interacción conversacional breve.
        if _is_simple_greeting(question):
            prompt_text = (
                "Responde como un asistente conversacional en español. "
                "El usuario te está saludando. Contesta de forma breve, "
                "natural y profesional, e invítalo a realizar una consulta."
            )
            logging.info("Saludo simple detectado; se omite la consulta a Neo4j.")
        else:
            # =====================================================
            # 1. Consultar Neo4j
            # =====================================================

            resultado_neo4j = select_medical_data(question)

            logging.info(
                "Consulta Neo4j completada | pregunta=%s | cmf=%s | "
                "concepto=%s | registros=%d",
                question,
                resultado_neo4j.get("cmf"),
                resultado_neo4j.get("concepto"),
                len(resultado_neo4j.get("data", []))
            )

            # =====================================================
            # 2. Convertir los resultados de Neo4j en contexto
            # =====================================================

            contexto = _generar_contexto_neo4j(
                resultado_neo4j,
                question
            )

            # =====================================================
            # 3. Construir prompt médico
            # =====================================================

            prompt_text = build_prompt(
                question,
                contexto=contexto
            )

        # =====================================================
        # 4. Consultar modelo de lenguaje
        # =====================================================

        effective_model = model or llm_service.get_default_model()

        respuesta = llm_service.chat(
            effective_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt_text
                }
            ]
        )

        # =====================================================
        # 5. Extraer respuesta
        # =====================================================

        answer_text = respuesta.get(
            "message",
            {}
        ).get(
            "content",
            str(respuesta)
        )

        # =====================================================
        # 6. Guardar resultado
        # =====================================================

        TASKS[task_id]["status"] = "finished"
        TASKS[task_id]["answer"] = answer_text

        logging.info(
            "Pregunta procesada correctamente: %s",
            task_id
        )

    except Exception as e:
        logging.exception(
            f"Error procesando pregunta {task_id}: {e}"
        )

        TASKS[task_id]["status"] = "error"
        TASKS[task_id]["error"] = str(e)


# Mount the frontend only after API routes so it cannot shadow /health or /patient-captures.
frontend_build = Path(__file__).resolve().parent.parent / "frontend" / "build"
if frontend_build.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(frontend_build), html=True), name="frontend")
    logging.info("Frontend static files mounted from %s", frontend_build)


# Flujo clínico: asignaciones médico-paciente y datos del embarazo.
app.include_router(clinical_workflow_router)
