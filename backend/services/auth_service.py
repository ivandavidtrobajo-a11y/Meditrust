import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from database.mongodb import get_db

SECRET_KEY = os.getenv("JWT_SECRET", "asjdlhidpafjasf546a7d9865as1d689641sad68")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_by_email(email: str):
    db = get_db()
    return db.users.find_one({"email": email})


def get_user_by_id(user_id: str):
    db = get_db()
    from bson.objectid import ObjectId
    return db.users.find_one({"_id": ObjectId(user_id)})


def create_user(name: str, email: str, password: str, role: str = "embarazada"):
    db = get_db()
    user = {
        "name": name,
        "email": email,
        "password": hash_password(password),
        "role": role,
        "is_active": True,
        "profile_image": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = db.users.insert_one(user)
    user["_id"] = str(result.inserted_id)
    return user


def update_user(email: str, updates: dict):
    db = get_db()
    updates["updated_at"] = datetime.utcnow()
    db.users.update_one({"email": email}, {"$set": updates})


def save_reset_token(email: str, token: str):
    db = get_db()
    db.password_resets.insert_one({
        "email": email,
        "token": token,
        "created_at": datetime.utcnow(),
    })


def get_reset_token(email: str, token: str):
    db = get_db()
    return db.password_resets.find_one({"email": email, "token": token})


def delete_reset_token(email: str):
    db = get_db()
    db.password_resets.delete_many({"email": email})
