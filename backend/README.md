 API de Análisis Inteligente de Documentos con FastAPI, MongoDB y LLM

 Descripción general

API REST desarrollada con FastAPI para consulta inteligente de archivos Excel utilizando modelos de lenguaje (LLM) y MongoDB.

El sistema está diseñado para:
- Almacenar documentos subidos por el usuario.
- Analizar su contenido generando contexto enriquecido vía LLM.
- Responder preguntas en lenguaje natural con datos reales de los documentos.

---

 Arquitectura general

- FastAPI: Framework principal de la API.
- MongoDB: Almacenamiento de documentos y metadatos.
- Ollama + Gemma 3:1b: Modelo de lenguaje para responder preguntas.
- Pandas: Procesamiento de archivos Excel.
- Multithreading: Consultas largas sin bloquear la API.

Flujo:

1. El usuario sube documentos Excel.
2. Se parsea el contenido y se genera contexto automáticamente con el LLM.
3. El usuario formula una pregunta.
4. Se recupera el contexto pre-generado desde MongoDB.
5. Se construye un prompt contextual.
6. El modelo de lenguaje genera una respuesta.
7. El usuario consulta el resultado de forma asíncrona.

---

 Estructura del proyecto

- main.py - Archivo principal de la API
- uploads/ - Carpeta donde se almacenan los archivos subidos
- services/
  - parser.py - Extracción de datos desde Excel a MongoDB
  - prompt.py - Construcción del prompt para el LLM
  - auth_service.py - Autenticación y JWT
  - email_service.py - Envío de correos (reset password)
- database/
  - mongodb.py - Conexión a MongoDB
  - datasets_db.py - CRUD de datasets médicos

---

## Proveedores de modelos de lenguaje

El backend admite tres proveedores mediante una interfaz común:

- **Ollama:** ejecución local.
- **Hugging Face:** inferencia online.
- **Gemini API:** inferencia online opcional, habilitada al configurar `GEMINI_API_KEY` en el entorno del backend.

La preferencia del modelo se almacena por usuario y conversación en MongoDB. El backend identifica al usuario mediante el JWT y valida que el modelo solicitado esté disponible. La clave de Gemini nunca debe enviarse al frontend.

Consulta [GEMINI_SETUP.md](./GEMINI_SETUP.md) para configurar la clave, desplegar y probar la integración. Para las pruebas cloud, utiliza datos sintéticos o anonimizados.


## Análisis multimodal de capturas de smartwatch (Fase 7C)

Las capturas de pacientes se almacenan primero en MongoDB GridFS. Cada imagen genera una tarea persistente en `capture_analysis_jobs`; el trabajador integrado en FastAPI reclama tareas atómicamente, crea ejecuciones en `capture_analysis_runs` y conserva las revisiones médicas en `capture_analysis_reviews`. Los reintentos sobreviven a reinicios porque el estado de la cola está en MongoDB.

### Variables de entorno

- `OPENROUTER_API_KEY`: credencial principal obligatoria para el análisis automático.
- `OPENROUTER_DEFAULT_MODEL`: modelo multimodal predeterminado; por defecto `openrouter/free`.
- `GEMINI_API_KEY`, `GEMINI_DEFAULT_MODEL`: adaptador Gemini opcional.
- `HF_API_TOKEN`, `HF_DEFAULT_MODEL`: adaptador Hugging Face opcional.
- `CAPTURE_MODELS_JSON`: catálogo JSON opcional que controla los modelos que el médico puede seleccionar. Si se define, reemplaza el catálogo generado desde las credenciales disponibles.
- `SMARTWATCH_CLINICAL_RULES_JSON`: reglas clínicas JSON aprobadas por profesionales sanitarios. Sin reglas configuradas, las capturas legibles quedan en revisión clínica; el sistema no las etiqueta como normales.
- `CAPTURE_ANALYSIS_MAX_ATTEMPTS`: máximo de intentos por tarea (5 por defecto).
- `CAPTURE_ANALYSIS_POLL_SECONDS`: intervalo de consulta de la cola (3 segundos por defecto).
- `CAPTURE_ANALYSIS_LEASE_MINUTES`: tiempo tras el que una tarea bloqueada se puede recuperar (10 minutos por defecto).

Ejemplo de catálogo (ajustar a los modelos multimodales realmente habilitados en las cuentas de cada proveedor):

```json
[
  {"id":"openrouter/free","name":"OpenRouter Free Router","provider":"openrouter"},
  {"id":"gemini-2.0-flash","name":"Gemini Flash","provider":"gemini"},
  {"id":"Qwen/Qwen2.5-VL-7B-Instruct","name":"Qwen Vision","provider":"huggingface"}
]
```

No se incluyen umbrales clínicos numéricos de ejemplo deliberadamente. El formato de configuración es un objeto cuyos campos coinciden con las claves de `readings`, por ejemplo `{"systolic_bp":{"min":null,"max":null},"diastolic_bp":{"min":null,"max":null},"heart_rate":{"min":null,"max":null},"spo2":{"min":null,"max":null}}`. Sustituir los valores `null` por límites definidos, documentados y validados por el equipo sanitario. Un campo sin umbrales válidos o una medición configurada que no pueda extraerse se envía a revisión; no se etiqueta como normal. La IA extrae datos visibles; no diagnostica preeclampsia ni sustituye una consulta clínica.

El trabajador de cola se inicia dentro del proceso FastAPI. MongoDB conserva los trabajos pendientes y los bloqueos son atómicos para permitir recuperación ante reinicios y evitar que dos instancias reclamen simultáneamente el mismo trabajo. En despliegue debe mantenerse al menos una instancia activa del servicio API para que el trabajador procese la cola.

Pruebas iniciales: utilizar únicamente imágenes sintéticas o anonimizadas. La activación para pacientes reales requiere validación clínica, revisión de privacidad y evaluación de los términos de retención y tratamiento de datos de cada proveedor.
