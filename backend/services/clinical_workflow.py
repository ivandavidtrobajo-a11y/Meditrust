import hashlib
import logging
import secrets
import string
import uuid
from datetime import date, datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from database.mongodb import get_db
from services.auth_service import decode_token, get_user_by_id

logger = logging.getLogger(__name__)
router = APIRouter(tags=["clinical-workflow"])
security = HTTPBearer()

CODE_TTL_HOURS = 48
CODE_ATTEMPT_WINDOW_MINUTES = 15
MAX_CODE_ATTEMPTS = 10
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class LinkCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=24)


class PregnancyUpdate(BaseModel):
    due_date: date
    gestational_week: int = Field(ge=0, le=42)


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")
    user = get_user_by_id(payload.get("id"))
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")
    return user


def _uid(user):
    return str(user.get("_id", user.get("id", "")))


def _require_role(user, role):
    if user.get("role", "embarazada") != role:
        raise HTTPException(status_code=403, detail="No tienes permisos para esta operación.")


def _patient_id_or_404(patient_id):
    try:
        return ObjectId(patient_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")


def _active_assignment(db, doctor_id, patient_id):
    return db.doctor_patient_assignments.find_one({
        "doctor_id": doctor_id,
        "patient_id": patient_id,
        "status": "active",
    })


def _audit(db, actor_id, action, patient_id=None, details=None):
    db.audit_logs.insert_one({
        "actor_id": actor_id,
        "action": action,
        "resource_type": "patient" if patient_id else "linking_code",
        "resource_id": patient_id,
        "details": details or {},
        "created_at": datetime.now(timezone.utc),
    })


def _sync_assignment_graph(doctor, patient, assignment, active=True):
    try:
        from database.neo4j import neo4j_connection
        neo4j_connection.execute_query(
            """
            MERGE (d:Doctor {id: $doctor_id})
            SET d.name = $doctor_name
            MERGE (p:Patient {id: $patient_id})
            SET p.name = $patient_name
            MERGE (d)-[r:SUPERVISES {assignment_id: $assignment_id}]->(p)
            SET r.status = $status,
                r.created_at = $created_at,
                r.deactivated_at = $deactivated_at
            """,
            {
                "doctor_id": assignment["doctor_id"],
                "doctor_name": doctor.get("name", ""),
                "patient_id": assignment["patient_id"],
                "patient_name": patient.get("name", ""),
                "assignment_id": assignment["assignment_id"],
                "status": "active" if active else "inactive",
                "created_at": assignment["created_at"].isoformat(),
                "deactivated_at": assignment.get("deactivated_at").isoformat()
                    if assignment.get("deactivated_at") else None,
            },
        )
    except Exception:
        logger.exception("No se pudo sincronizar la asignación con Neo4j; MongoDB conserva el estado principal.")


def _sync_pregnancy_graph(patient_id, pregnancy):
    try:
        from database.neo4j import neo4j_connection
        neo4j_connection.execute_query(
            """
            MERGE (p:Patient {id: $patient_id})
            MERGE (g:Pregnancy {patient_id: $patient_id})
            SET g.due_date = $due_date,
                g.gestational_week = $gestational_week,
                g.updated_at = $updated_at
            MERGE (p)-[:HAS_PREGNANCY]->(g)
            """,
            {
                "patient_id": patient_id,
                "due_date": pregnancy["due_date"],
                "gestational_week": pregnancy["gestational_week"],
                "updated_at": pregnancy["updated_at"].isoformat(),
            },
        )
    except Exception:
        logger.exception("No se pudo sincronizar el embarazo con Neo4j; MongoDB conserva el estado principal.")


@router.on_event("startup")
def ensure_workflow_indexes():
    try:
        db = get_db()
        db.linking_codes.create_index("code_hash", unique=True)
        db.linking_codes.create_index("expires_at", expireAfterSeconds=0)
        db.doctor_patient_assignments.create_index(
            [("doctor_id", 1), ("patient_id", 1), ("status", 1)]
        )
        db.patient_profiles.create_index("patient_id", unique=True)
        db.audit_logs.create_index([("actor_id", 1), ("created_at", -1)])
    except Exception:
        logger.exception("No se pudieron crear todos los índices del flujo clínico.")


@router.post("/doctor/linking-codes")
def create_linking_code(user=Depends(current_user)):
    _require_role(user, "medico")
    db = get_db()
    doctor_id = _uid(user)
    raw_code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=CODE_TTL_HOURS)
    db.linking_codes.insert_one({
        "code_hash": code_hash,
        "doctor_id": doctor_id,
        "created_at": now,
        "expires_at": expires_at,
        "used_at": None,
        "used_by": None,
    })
    _audit(db, doctor_id, "linking_code.created", details={"expires_at": expires_at.isoformat()})
    return {
        "code": raw_code,
        "expires_at": expires_at.isoformat(),
        "expires_in_hours": CODE_TTL_HOURS,
        "single_use": True,
    }


@router.post("/patient/link")
def redeem_linking_code(request: LinkCodeRequest, user=Depends(current_user)):
    _require_role(user, "embarazada")
    db = get_db()
    patient_id = _uid(user)
    now = datetime.now(timezone.utc)

    attempts = db.linking_code_attempts.find_one({"_id": patient_id})
    window_started_at = attempts.get("window_started_at") if attempts else None
    if window_started_at and window_started_at.tzinfo is None:
        window_started_at = window_started_at.replace(tzinfo=timezone.utc)
    if attempts and window_started_at and now - window_started_at < timedelta(minutes=CODE_ATTEMPT_WINDOW_MINUTES):
        if attempts.get("attempts", 0) >= MAX_CODE_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Demasiados intentos. Espera 15 minutos.")
        db.linking_code_attempts.update_one({"_id": patient_id}, {"$inc": {"attempts": 1}})
    else:
        db.linking_code_attempts.update_one(
            {"_id": patient_id},
            {"$set": {"attempts": 1, "window_started_at": now}},
            upsert=True,
        )

    normalized = "".join(ch for ch in request.code.upper() if ch.isalnum())
    code_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    code_record = db.linking_codes.find_one_and_update(
        {
            "code_hash": code_hash,
            "used_at": None,
            "expires_at": {"$gt": now},
        },
        {"$set": {"used_at": now, "used_by": patient_id}},
        return_document=ReturnDocument.AFTER,
    )
    if not code_record:
        raise HTTPException(status_code=400, detail="Código inválido, vencido o ya utilizado.")

    doctor = db.users.find_one({"_id": _patient_id_or_404(code_record["doctor_id"]), "role": "medico"})
    patient = db.users.find_one({"_id": _patient_id_or_404(patient_id), "role": "embarazada"})
    if not doctor or not patient:
        raise HTTPException(status_code=400, detail="No se pudo validar la cuenta asociada al código.")

    existing = _active_assignment(db, code_record["doctor_id"], patient_id)
    if existing:
        return {"message": "Ya existe una vinculación activa con este médico.", "assignment_id": existing["assignment_id"]}

    assignment = {
        "assignment_id": str(uuid.uuid4()),
        "doctor_id": code_record["doctor_id"],
        "patient_id": patient_id,
        "status": "active",
        "created_at": now,
        "deactivated_at": None,
        "created_via": "linking_code",
        "linking_code_id": str(code_record["_id"]),
    }
    db.doctor_patient_assignments.insert_one(assignment)
    _audit(db, patient_id, "doctor_patient_assignment.created", patient_id,
           {"doctor_id": code_record["doctor_id"], "assignment_id": assignment["assignment_id"]})
    _sync_assignment_graph(doctor, patient, assignment, active=True)
    return {"message": "Vinculación realizada correctamente.", "assignment_id": assignment["assignment_id"]}


@router.get("/doctor/patients")
def list_doctor_patients(user=Depends(current_user)):
    _require_role(user, "medico")
    db = get_db()
    doctor_id = _uid(user)
    assignments = list(db.doctor_patient_assignments.find({
        "doctor_id": doctor_id, "status": "active"
    }).sort("created_at", -1))
    result = []
    for assignment in assignments:
        try:
            patient = db.users.find_one(
                {"_id": ObjectId(assignment["patient_id"]), "role": "embarazada"},
                {"name": 1, "email": 1},
            )
        except (InvalidId, TypeError):
            patient = None
        if not patient:
            continue
        profile = db.patient_profiles.find_one({"patient_id": assignment["patient_id"]}, {"_id": 0})
        result.append({
            "patient_id": assignment["patient_id"],
            "name": patient.get("name", ""),
            "email": patient.get("email", ""),
            "assignment_id": assignment["assignment_id"],
            "assigned_at": assignment["created_at"].isoformat(),
            "pregnancy": {
                "due_date": profile.get("due_date") if profile else None,
                "gestational_week": profile.get("gestational_week") if profile else None,
                "updated_at": profile.get("updated_at").isoformat() if profile and profile.get("updated_at") else None,
            },
        })
    return {"patients": result, "total": len(result)}


@router.get("/doctor/patients/{patient_id}")
def get_doctor_patient(patient_id: str, user=Depends(current_user)):
    _require_role(user, "medico")
    db = get_db()
    doctor_id = _uid(user)
    if not _active_assignment(db, doctor_id, patient_id):
        raise HTTPException(status_code=403, detail="No tienes una asignación activa con este paciente.")
    patient = db.users.find_one(
        {"_id": _patient_id_or_404(patient_id), "role": "embarazada"},
        {"name": 1, "email": 1, "created_at": 1},
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")
    profile = db.patient_profiles.find_one({"patient_id": patient_id}, {"_id": 0})
    captures_count = db.patient_capture_records.count_documents({"patient_id": patient_id})
    return {
        "patient": {"id": patient_id, "name": patient.get("name", ""), "email": patient.get("email", "")},
        "pregnancy": profile,
        "captures_count": captures_count,
    }


@router.delete("/doctor/patients/{patient_id}/assignment")
def deactivate_patient_assignment(patient_id: str, user=Depends(current_user)):
    _require_role(user, "medico")
    db = get_db()
    doctor_id = _uid(user)
    assignment = _active_assignment(db, doctor_id, patient_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="No existe una asignación activa con este paciente.")
    now = datetime.now(timezone.utc)
    db.doctor_patient_assignments.update_one(
        {"_id": assignment["_id"], "status": "active"},
        {"$set": {"status": "inactive", "deactivated_at": now}},
    )
    assignment["status"] = "inactive"
    assignment["deactivated_at"] = now
    doctor = user
    patient = db.users.find_one({"_id": _patient_id_or_404(patient_id)})
    _audit(db, doctor_id, "doctor_patient_assignment.deactivated", patient_id,
           {"assignment_id": assignment["assignment_id"]})
    if patient:
        _sync_assignment_graph(doctor, patient, assignment, active=False)
    return {"message": "Asignación desactivada. El historial se conserva."}


@router.get("/patient/relationships")
def patient_relationships(user=Depends(current_user)):
    _require_role(user, "embarazada")
    db = get_db()
    patient_id = _uid(user)
    assignments = list(db.doctor_patient_assignments.find({
        "patient_id": patient_id, "status": "active"
    }).sort("created_at", -1))
    doctors = []
    for assignment in assignments:
        try:
            doctor = db.users.find_one(
                {"_id": ObjectId(assignment["doctor_id"]), "role": "medico"},
                {"name": 1, "email": 1},
            )
        except (InvalidId, TypeError):
            doctor = None
        if doctor:
            doctors.append({
                "id": assignment["doctor_id"],
                "name": doctor.get("name", ""),
                "email": doctor.get("email", ""),
                "assigned_at": assignment["created_at"].isoformat(),
            })
    return {"doctors": doctors}


@router.get("/patient/pregnancy")
def get_patient_pregnancy(user=Depends(current_user)):
    _require_role(user, "embarazada")
    profile = get_db().patient_profiles.find_one({"patient_id": _uid(user)}, {"_id": 0})
    return {"pregnancy": profile}


@router.put("/doctor/patients/{patient_id}/pregnancy")
def update_patient_pregnancy(patient_id: str, request: PregnancyUpdate, user=Depends(current_user)):
    _require_role(user, "medico")
    db = get_db()
    doctor_id = _uid(user)
    if not _active_assignment(db, doctor_id, patient_id):
        raise HTTPException(status_code=403, detail="No tienes una asignación activa con este paciente.")
    _patient_id_or_404(patient_id)
    patient = db.users.find_one({"_id": ObjectId(patient_id), "role": "embarazada"})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")

    now = datetime.now(timezone.utc)
    pregnancy = {
        "patient_id": patient_id,
        "due_date": request.due_date.isoformat(),
        "gestational_week": request.gestational_week,
        "updated_at": now,
        "updated_by": doctor_id,
    }
    db.patient_profiles.update_one(
        {"patient_id": patient_id},
        {"$set": pregnancy, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    _audit(db, doctor_id, "pregnancy.updated", patient_id, {
        "due_date": pregnancy["due_date"],
        "gestational_week": pregnancy["gestational_week"],
    })
    _sync_pregnancy_graph(patient_id, pregnancy)
    return {
        "message": "Datos del embarazo actualizados.",
        "pregnancy": {
            "due_date": pregnancy["due_date"],
            "gestational_week": pregnancy["gestational_week"],
            "updated_at": now.isoformat(),
        },
    }
