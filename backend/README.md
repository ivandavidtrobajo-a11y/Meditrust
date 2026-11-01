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
