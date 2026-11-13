import base64, json, logging, os, re, threading, time
from datetime import datetime, timedelta, timezone
import requests
from bson import ObjectId
from gridfs import GridFSBucket
from pymongo import ReturnDocument
from database.mongodb import get_db

logger = logging.getLogger(__name__)
PROMPT_VERSION = "capture-extraction-v1"
SYSTEM_PROMPT = """Extrae exclusivamente datos visibles de la imagen. No diagnostiques ni infieras enfermedades. Devuelve JSON válido: {"readings":{"systolic_bp":null,"diastolic_bp":null,"heart_rate":null,"spo2":null,"measurement_time":null,"units":{}},"image_quality":"readable|unreadable|partial","uncertainties":[],"notes":""}. Valores numéricos como números; ausentes como null. No emitas recomendaciones clínicas."""

def now():
    return datetime.now(timezone.utc)

def rules():
    try:
        value=json.loads(os.getenv("SMARTWATCH_CLINICAL_RULES_JSON","{}"))
        return value if isinstance(value,dict) else {}
    except ValueError:
        logger.exception("Reglas clínicas inválidas")
        return {}

def parse_json(content):
    if isinstance(content,list):
        content="".join(p.get("text","") for p in content if isinstance(p,dict))
    value=str(content or "").strip()
    value=re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$","",value,flags=re.I)
    try:
        return json.loads(value)
    except ValueError:
        match=re.search(r"\{.*\}",value,re.S)
        if not match:
            raise ValueError("El modelo no devolvió JSON interpretable.")
        return json.loads(match.group(0))

def call_provider(provider,model,image_bytes,mime):
    encoded=base64.b64encode(image_bytes).decode("ascii")
    data_url="data:"+mime+";base64,"+encoded
    user_content=[{"type":"text","text":"Extrae las mediciones visibles."},{"type":"image_url","image_url":{"url":data_url}}]
    if provider in ("openrouter","huggingface"):
        if provider=="openrouter":
            key=os.getenv("OPENROUTER_API_KEY","")
            url="https://openrouter.ai/api/v1/chat/completions"
        else:
            key=os.getenv("HF_API_TOKEN","")
            url="https://router.huggingface.co/v1/chat/completions"
        if not key:
            raise RuntimeError("Falta la credencial del proveedor "+provider+".")
        headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"}
        if provider=="openrouter":
            headers["X-Title"]="Meditrust"
        response=requests.post(url,headers=headers,json={"model":model,"temperature":0,"max_tokens":1200,"messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_content}]},timeout=(15,120))
        response.raise_for_status()
        raw=response.json()
        return raw["choices"][0]["message"]["content"],raw
    if provider=="gemini":
        key=os.getenv("GEMINI_API_KEY","")
        if not key:
            raise RuntimeError("Falta GEMINI_API_KEY.")
        payload={"systemInstruction":{"parts":[{"text":SYSTEM_PROMPT}]},"contents":[{"role":"user","parts":[{"text":"Extrae las mediciones visibles."},{"inlineData":{"mimeType":mime,"data":encoded}}]}],"generationConfig":{"temperature":0,"maxOutputTokens":1200,"responseMimeType":"application/json"}}
        response=requests.post("https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent",headers={"x-goog-api-key":key,"Content-Type":"application/json"},json=payload,timeout=(15,120))
        response.raise_for_status()
        raw=response.json()
        return "".join(p.get("text","") for p in raw["candidates"][0]["content"]["parts"]),raw
    raise ValueError("Proveedor no permitido.")

def classify(readings,quality,uncertainties):
    if quality!="readable" or uncertainties:
        return "analysis_failed",["La imagen o su interpretación requieren revisión."]
    configured=rules()
    if not configured:
        return "needs_review",["No hay criterios clínicos aprobados configurados."]
    alerts=[]
    for field,bounds in configured.items():
        if not isinstance(bounds,dict) or (bounds.get("min") is None and bounds.get("max") is None):
            alerts.append("No hay umbrales clínicos válidos configurados para "+field+".")
            continue
        value=readings.get(field)
        if value is None:
            alerts.append("No se pudo extraer el dato configurado: "+field+".")
            continue
        try:
            number=float(value)
            if bounds.get("min") is not None and number<float(bounds["min"]):
                alerts.append(field+" por debajo del umbral configurado.")
            if bounds.get("max") is not None and number>float(bounds["max"]):
                alerts.append(field+" por encima del umbral configurado.")
        except (ValueError,TypeError):
            alerts.append(field+" no pudo validarse.")
    return ("needs_review",alerts) if alerts else ("no_alerts_detected",[])

def serialize(v):
    if isinstance(v,ObjectId): return str(v)
    if isinstance(v,datetime): return v.isoformat()
    if isinstance(v,dict): return {str(k):serialize(x) for k,x in v.items()}
    if isinstance(v,list): return [serialize(x) for x in v]
    return v

class CaptureAnalysisManager:
    def __init__(self):
        self.thread=None
        self.stop_event=threading.Event()
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear()
        self.thread=threading.Thread(target=self.loop,name="capture-analysis-worker",daemon=True)
        self.thread.start()
    def enqueue(self,patient_id,gridfs_id,filename,provider="openrouter",model=None,actor_id=None,job_type="automatic"):
        model=model or os.getenv("OPENROUTER_DEFAULT_MODEL","openrouter/free")
        db=get_db(); stamp=now()
        result=db.capture_analysis_jobs.insert_one({"patient_id":patient_id,"gridfs_id":gridfs_id,"filename":filename,"provider":provider,"model":model,"status":"queued","attempts":0,"max_attempts":int(os.getenv("CAPTURE_ANALYSIS_MAX_ATTEMPTS", "5")),"created_at":stamp,"updated_at":stamp,"next_attempt_at":stamp,"requested_by":actor_id,"job_type":job_type})
        db.patient_capture_records.update_one({"patient_id":patient_id,"gridfs_id":gridfs_id},{"$set":{"analysis_status":"queued","analysis_updated_at":stamp}})
        return str(result.inserted_id)
    def claim(self):
        db=get_db(); stamp=now()
        stale=stamp-timedelta(minutes=int(os.getenv("CAPTURE_ANALYSIS_LEASE_MINUTES","10")))
        db.capture_analysis_jobs.update_many({"status":"processing","locked_at":{"$lt":stale}},{"$set":{"status":"queued","next_attempt_at":stamp},"$unset":{"locked_at":""}})
        return db.capture_analysis_jobs.find_one_and_update({"status":{"$in":["queued","retry"]},"next_attempt_at":{"$lte":stamp}},{"$set":{"status":"processing","locked_at":stamp,"updated_at":stamp}},sort=[("created_at",1)],return_document=ReturnDocument.AFTER)
    def loop(self):
        while not self.stop_event.is_set():
            try:
                job=self.claim()
                if job:
                    self.process(job)
                else:
                    self.stop_event.wait(float(os.getenv("CAPTURE_ANALYSIS_POLL_SECONDS", "3")))
            except Exception:
                logger.exception("Error en trabajador de capturas")
                self.stop_event.wait(float(os.getenv("CAPTURE_ANALYSIS_POLL_SECONDS", "3")))
    def process(self,job):
        db=get_db(); started=now()
        run={"job_id":job["_id"],"patient_id":job["patient_id"],"gridfs_id":job["gridfs_id"],"provider":job["provider"],"model":job["model"],"prompt_version":PROMPT_VERSION,"attempt":job.get("attempts",0)+1,"status":"processing","started_at":started,"requested_by":job.get("requested_by"),"job_type":job.get("job_type","automatic")}
        run_id=db.capture_analysis_runs.insert_one(run).inserted_id
        db.patient_capture_records.update_one(
            {"patient_id":job["patient_id"],"gridfs_id":job["gridfs_id"]},
            {"$set":{"analysis_status":"processing","analysis_updated_at":started}})
        try:
            bucket=GridFSBucket(db,bucket_name="patient_capture_images")
            stream=bucket.open_download_stream(ObjectId(job["gridfs_id"]))
            try:
                image=stream.read()
                mime=(stream.metadata or {}).get("content_type","image/jpeg")
            finally: stream.close()
            content,raw=call_provider(job["provider"],job["model"],image,mime)
            parsed=parse_json(content)
            readings=parsed.get("readings",{})
            if not isinstance(readings,dict): raise ValueError("Estructura de mediciones inválida.")
            uncertainties=parsed.get("uncertainties",[])
            if not isinstance(uncertainties,list): uncertainties=[str(uncertainties)]
            state,reasons=classify(readings,parsed.get("image_quality","partial"),uncertainties)
            finished=now()
            db.capture_analysis_runs.update_one({"_id":run_id},{"$set":{"status":"completed" if state!="analysis_failed" else "analysis_failed","raw_response":raw,"model_content":content,"resolved_model":raw.get("model") if isinstance(raw,dict) else None,"readings":readings,"image_quality":parsed.get("image_quality"),"uncertainties":uncertainties,"classification":state,"review_reasons":reasons,"finished_at":finished,"duration_ms":int((finished-started).total_seconds()*1000)}})
            db.patient_capture_records.update_one({"patient_id":job["patient_id"],"gridfs_id":job["gridfs_id"]},{"$set":{"analysis_status":state,"latest_run_id":str(run_id),"analysis_updated_at":finished}})
            db.capture_analysis_jobs.update_one({"_id":job["_id"]},{"$set":{"status":"completed" if state!="analysis_failed" else "failed","last_run_id":run_id,"updated_at":finished},"$unset":{"locked_at":""}})
        except Exception as exc:
            logger.exception("Falló análisis de captura %s",job.get("gridfs_id"))
            attempts=int(job.get("attempts",0))+1; finished=now()
            db.capture_analysis_runs.update_one({"_id":run_id},{"$set":{"status":"provider_error","error":str(exc)[:1500],"finished_at":finished}})
            final=attempts>=int(job.get("max_attempts",5))
            delay=min(3600,30*(2**(attempts-1)))
            db.capture_analysis_jobs.update_one({"_id":job["_id"]},{"$set":{"status":"failed" if final else "retry","attempts":attempts,"last_error":str(exc)[:1500],"updated_at":finished,"next_attempt_at":finished+timedelta(seconds=delay)},"$unset":{"locked_at":""}})
            db.patient_capture_records.update_one({"patient_id":job["patient_id"],"gridfs_id":job["gridfs_id"]},{"$set":{"analysis_status":"analysis_failed" if final else "retrying","analysis_updated_at":finished}})
    def history(self,patient_id,gridfs_id=None,include_raw=False):
        query={"patient_id":patient_id}
        if gridfs_id: query["gridfs_id"]=gridfs_id
        projection=None if include_raw else {"raw_response":0,"model_content":0}
        return [serialize(x) for x in get_db().capture_analysis_runs.find(query,projection).sort("started_at",-1).limit(200)]
    def reviews(self,patient_id,gridfs_id=None):
        query={"patient_id":patient_id}
        if gridfs_id: query["gridfs_id"]=gridfs_id
        return [serialize(x) for x in get_db().capture_analysis_reviews.find(query).sort("reviewed_at",-1).limit(100)]

manager=CaptureAnalysisManager()
