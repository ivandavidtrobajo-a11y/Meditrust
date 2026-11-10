from fastapi import HTTPException, status

SUPPORTED_ROLES = {"embarazada", "medico", "admin"}

def _user_id(user: dict) -> str:
    return str(user.get("_id", user.get("id", "")))

def _role(user: dict) -> str:
    return str(user.get("role", "embarazada")).strip().lower()

def require_role(current_user: dict, *allowed_roles: str) -> dict:
    role = _role(current_user)
    if role not in SUPPORTED_ROLES or role not in set(allowed_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para realizar esta operación.")
    return current_user

def require_admin(current_user: dict) -> dict:
    return require_role(current_user, "admin")

def require_patient_access(current_user: dict, patient_id: str, database=None) -> dict:
    """Paciente: solo sus registros. Médico: solo pacientes con asignación activa."""
    role, current_id = _role(current_user), _user_id(current_user)
    if role == "embarazada":
        if patient_id != current_id:
            raise HTTPException(status_code=403, detail="Solo puedes consultar tus propios registros.")
        return current_user
    if role == "medico":
        if database is None:
            raise RuntimeError("Se necesita la base de datos para verificar la asignación médica.")
        assignment = database["doctor_patient_assignments"].find_one({
            "doctor_id": current_id, "patient_id": patient_id,
            "$or": [{"status": "active"}, {"active": True}],
        })
        if assignment is None:
            raise HTTPException(status_code=403, detail="No tienes una asignación activa con este paciente.")
        return current_user
    raise HTTPException(status_code=403, detail="Este perfil no tiene acceso a datos clínicos de pacientes.")
