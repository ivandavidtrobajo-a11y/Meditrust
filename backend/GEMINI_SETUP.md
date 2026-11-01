# Configuración de Gemini API en Meditrust

## 1. Variables de entorno del backend

Configura estas variables en el entorno del servicio FastAPI (por ejemplo, en **Render → servicio del backend → Environment**):

| Variable | Valor | Obligatoria |
|---|---|---|
| `GEMINI_API_KEY` | Clave creada en Google AI Studio | Sí, para habilitar Gemini |
| `GEMINI_DEFAULT_MODEL` | `gemini-2.5-flash` | No |

La clave debe existir únicamente en el backend. **No** la guardes en React, en una variable `VITE_*`, en el repositorio ni en archivos versionados. No compartas la clave en capturas de pantalla o mensajes.

Si `GEMINI_API_KEY` no está configurada, Gemini no aparecerá en el selector y Ollama/Hugging Face seguirán disponibles como antes. `GEMINI_DEFAULT_MODEL` solo cambia el modelo predeterminado cuando la clave de Gemini está configurada; si se omite, se conserva la selección predeterminada previa del proyecto.

No se añadió una dependencia nueva: el proveedor utiliza `requests`, que ya está incluido en `backend/requirements.txt`.

## 2. Selección por usuario y conversación

- El frontend genera un identificador para la conversación activa y lo conserva en el navegador.
- El backend obtiene la identidad del usuario desde el JWT; el frontend no envía un identificador de usuario manipulable.
- MongoDB guarda la preferencia en la colección `chat_preferences`, asociada a `user_id` y `conversation_id`.
- Al cambiar el modelo, el frontend guarda la selección mediante `PUT /chat/preferences`.
- Al abrir el chat, recupera la preferencia con `GET /chat/preferences/{conversation_id}`.
- El botón **Nueva conversación** crea otro identificador y, por tanto, una preferencia independiente.
- `/ask/`, `/result/{task_id}` y `/cancel/{task_id}` requieren el JWT y las tareas solo pueden consultarse o cancelarse por el usuario que las inició.

La colección de preferencias es independiente de los datos médicos de MongoDB y de las consultas a Neo4j. El proveedor LLM sigue recibiendo el contexto que construye el backend a partir de Neo4j; Gemini no sustituye la consulta ni se inventa los registros.

## 3. Prueba de integración

1. Configura `GEMINI_API_KEY` en el backend y vuelve a desplegarlo.
2. Inicia sesión en Meditrust y abre el chat.
3. Comprueba que el selector muestra la sección **Gemini API (online)**.
4. Selecciona Gemini y realiza una prueba con información sintética, por ejemplo: «Explica qué significa un valor ficticio de 12 consultas en un CMF de prueba».
5. Cambia a Ollama o Hugging Face y comprueba que el selector sigue permitiendo usar esos proveedores.
6. Inicia una nueva conversación, selecciona otro modelo y verifica que la preferencia de la conversación anterior no cambia.

Para revisar errores, consulta los logs del servicio backend. Los errores HTTP de Gemini se registran con el código y el detalle devuelto por Google, pero la clave API no se incluye en el mensaje de error.

## 4. Protección de datos

Esta integración no cambia las bases de datos clínicas ni el flujo de consulta de Neo4j. Sin embargo, al seleccionar un proveedor cloud, el prompt y el contexto enviado al modelo salen del entorno de Meditrust y se transmiten a Google. Para pruebas, utiliza datos sintéticos o anonimizados. No envíes historias clínicas identificables a una API cloud sin la autorización, evaluación de privacidad y garantías institucionales correspondientes.

## 5. Referencias técnicas

- [Gemini API: referencia general y autenticación](https://ai.google.dev/api)
- [Gemini API: generateContent](https://ai.google.dev/api/generate-content)
