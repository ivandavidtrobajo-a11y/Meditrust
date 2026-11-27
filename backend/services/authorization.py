from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from services.auth_service import decode_token, get_user_by_id

SUPPORTED_ROLES = {"embarazada", "medico", "admin"}
security = HTTPBearer(auto_error=False)


def _user_id(user: dict) -> str:
    return str(user.get("_id", user.get("id", "")))


def normalize_role(role) -> str:
    """Normaliza roles conocidos; los valores ausentes no reciben privilegios por defecto."""
    return str(role or "").strip().lower()


def _role(user: dict) -> str:
    return normalize_role(user.get("role"))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Resuelve una única identidad autenticada, activa y con rol reconocido."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales de autenticación requeridas.")

    payload = decode_token(credentials.credentials)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado.")

    user_id = payload.get("id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin identificador de usuario válido.")

    try:
        user = get_user_by_id(user_id)
    except (TypeError, ValueError):
        user = None

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado.")

    require_active_user(user)
    role = _role(user)
    if role not in SUPPORTED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La cuenta no tiene un rol válido. Contacta con un administrador.")

    # Entrega una representación canónica del rol a todas las rutas.
    user["role"] = role
    return user


def require_role(current_user: dict, *allowed_roles: str) -> dict:
    role = _role(current_user)
    normalized_allowed = {normalize_role(item) for item in allowed_roles}
    if role not in SUPPORTED_ROLES or role not in normalized_allowed:
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


def require_active_patient_assignment(patient_id: str, database) -> None:
    """Exige que la paciente tenga al menos una vinculación médica activa."""
    assignment = database["doctor_patient_assignments"].find_one(
        {"patient_id": str(patient_id), "status": "active"},
        {"_id": 1},
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Para subir nuevas capturas necesitas tener al menos un médico "
                "vinculado con una asignación activa. Vincula tu cuenta con el "
                "código proporcionado por tu médico."
            ),
        )


def require_active_user(current_user: dict) -> dict:
    """Rechaza cuentas desactivadas; los registros antiguos sin is_active siguen activos."""
    if current_user.get("is_active", True) is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta cuenta está desactivada. Contacta con un administrador.")
    return current_user
