# Prueba de captura de imágenes de pacientes

## Qué incorpora esta rama

- Interfaz React en la ruta `/patient-capture`.
- Endpoint autenticado `POST /patient-captures/`.
- Almacenamiento de los bytes en MongoDB GridFS y metadatos en `patient_capture_records`.
- Endpoint autenticado `GET /patient-captures/{patient_id}` que devuelve metadatos subidos por el usuario actual.
- Endpoint `GET /health` para comprobar que el proceso FastAPI responde.

## Ejecutar localmente

### Backend

Desde la carpeta `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Configura `MONGO_URI` y `MONGO_DB` en un archivo `.env` local, sin subirlo al repositorio. El backend requiere acceso a MongoDB para iniciar correctamente.

Comprobación: abre `http://127.0.0.1:8000/health`. Debe devolver JSON con `status: ok`.

### Frontend

Desde la carpeta `frontend`:

```powershell
npm ci
$env:VITE_AI_API_URL="http://127.0.0.1:8000"
npm run dev
```

Inicia sesión en la aplicación y abre `/patient-capture`. El endpoint requiere un token válido en `localStorage`.

## Probar la captura

1. Utiliza un ID sintético, por ejemplo `PACIENTE-DEMO-001`.
2. Selecciona de 1 a 5 imágenes JPEG, PNG o WEBP, de máximo 8 MB cada una.
3. Envía el formulario.
4. Verifica el mensaje de éxito y los nombres de los archivos guardados.
5. Comprueba en MongoDB la colección `patient_capture_records` y el bucket GridFS `patient_capture_images.files`.
6. Comprueba `GET /patient-captures/PACIENTE-DEMO-001` con el mismo token.

## Configuración de despliegue

- En Render, configura `VITE_AI_API_URL` para el frontend con la URL pública del backend **antes de compilar el frontend**.
- En el backend configura `MONGO_URI`, `MONGO_DB` y las variables de autenticación ya requeridas por el proyecto.
- Configura `CORS_ORIGINS` con el dominio exacto del frontend; se permiten varios orígenes separados por comas. No uses `*` con credenciales.
- Si necesitas crear un administrador inicial, configura `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` y, opcionalmente, `BOOTSTRAP_ADMIN_NAME`. No existe una contraseña administrativa predeterminada en esta rama.
- Configura el servicio de Render para desplegar la rama `feature/captura-paciente-hl7` durante la prueba, o revisa e integra los cambios en la rama de despliegue siguiendo el flujo del equipo.
- Vuelve a desplegar frontend y backend después de seleccionar la rama correcta. El despliegue no se ha ejecutado desde este cambio.

## Límites conocidos de esta versión

- La prueba almacena imágenes y metadatos; no realiza OCR, lectura automática de signos vitales ni diagnóstico.
- La consulta de metadatos está limitada a las capturas subidas por el usuario autenticado.
- No hay todavía endpoint de descarga/visualización desde GridFS ni interfaz de historial.
- No debe usarse con información real de pacientes hasta completar una revisión de seguridad y privacidad.
- Esta rama aún debe pasar una instalación limpia y pruebas en el despliegue real antes de afirmar que el sistema está listo desde cero.
