import logging
from datetime import datetime
from database.mongodb import get_db


def save_dataset(doc: dict) -> str:
    db = get_db()
    doc["created_at"] = doc.get("created_at", datetime.utcnow())
    result = db.datasets.insert_one(doc)
    return str(result.inserted_id)


def get_latest_dataset() -> dict:
    db = get_db()
    return db.datasets.find_one(sort=[("created_at", -1)])


def get_all_datasets() -> list:
    db = get_db()
    return list(db.datasets.find(sort=[("created_at", -1)]))


def get_dataset_by_id(dataset_id: str) -> dict:
    from bson.objectid import ObjectId
    db = get_db()
    return db.datasets.find_one({"_id": ObjectId(dataset_id)})


def delete_dataset(dataset_id: str) -> bool:
    from bson.objectid import ObjectId
    db = get_db()
    try:
        db.datasets.delete_one({"_id": ObjectId(dataset_id)})
        return True
    except Exception as e:
        logging.error(f"Error eliminando dataset: {e}")
        return False


def save_document_node(nombre, ruta, contenido):
    db = get_db()
    db.documents.insert_one({
        "nombre": nombre,
        "ruta": ruta,
        "contenido": contenido,
        "created_at": datetime.utcnow(),
    })
    return None


def list_document_nodes():
    db = get_db()
    res = list(db.documents.find({}, {"nombre": 1, "ruta": 1}))
    for r in res:
        r["id"] = str(r.pop("_id"))
    return res


def delete_document_node(id_str):
    from bson.objectid import ObjectId
    db = get_db()
    try:
        db.documents.delete_one({"_id": ObjectId(id_str)})
        return True
    except Exception:
        return False
