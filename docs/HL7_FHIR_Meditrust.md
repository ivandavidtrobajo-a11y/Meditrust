# HL7 y FHIR: propuesta de interoperabilidad para Meditrust

**Proyecto:** Meditrust  
**Estado:** documento de investigación y propuesta técnica inicial  
**Alcance:** preparar una primera integración interoperable sin sustituir MongoDB, Neo4j ni el backend actual.

## 1. Resumen ejecutivo

HL7 (Health Level Seven International) desarrolla estándares para el intercambio, la integración y la recuperación de información sanitaria. Para una aplicación web moderna, el punto de partida recomendado es **HL7 FHIR (Fast Healthcare Interoperability Resources)**. FHIR define recursos de información clínica y mecanismos de intercambio, incluida una API REST y representaciones JSON/XML.

En Meditrust, FHIR puede actuar como una capa de interoperabilidad entre FastAPI y otros sistemas sanitarios compatibles. No es una base de datos ni una alternativa a MongoDB o Neo4j: especifica cómo representar e intercambiar información de salud.

## 2. Estándares HL7: distinción básica

- **HL7 v2:** mensajes clínicos ampliamente utilizados para integrar sistemas hospitalarios, por ejemplo, admisiones, altas, transferencias y resultados.
- **HL7 CDA:** arquitectura para documentos clínicos estructurados.
- **HL7 FHIR:** recursos modulares y APIs para intercambiar información clínica, con formatos como JSON y XML.

FHIR es el candidato más práctico para una primera API de Meditrust, pero la versión concreta (por ejemplo, R4 o R5) debe elegirse según los requisitos del sistema externo con el que se vaya a integrar. No debe suponerse que dos sistemas usan la misma versión o los mismos perfiles.

## 3. Recursos FHIR pertinentes

| Recurso | Uso propuesto en Meditrust | Consideraciones |
|---|---|---|
| `Patient` | Identificación y datos demográficos mínimos del paciente. | Usar identificadores de prueba durante el desarrollo; definir reglas de identidad y duplicados antes de producción. |
| `Observation` | Mediciones como frecuencia cardíaca, presión arterial o saturación de oxígeno. | Cada medición debe tener valor, unidad, fecha y contexto válidos. Para interoperabilidad, usar códigos y unidades acordados, como LOINC y UCUM cuando corresponda. |
| `Device` | Identificar el smartwatch o dispositivo que originó una medición. | Registrar fabricante/modelo si se conoce; no inferir datos ausentes de una fotografía. |
| `DiagnosticReport` | Agrupar resultados e informes clínicos cuando el flujo futuro lo requiera. | No necesario para la primera iteración de captura de imágenes. |
| `DocumentReference` | Referenciar documentos o archivos clínicos asociados al paciente. | Es relevante para adjuntos, pero requiere definir seguridad, tipo de documento y acceso al contenido. |

Una fotografía de una pantalla del smartwatch **no equivale automáticamente a una Observation validada**. La primera fase almacena la imagen y sus metadatos; la extracción de valores mediante OCR/visión, su validación y su conversión a FHIR deben tratarse como una fase posterior.

## 4. Arquitectura de integración propuesta

1. **Frontend React:** permite que un usuario autenticado envíe imágenes o introduzca datos estructurados.
2. **FastAPI:** valida la solicitud, la identidad del usuario, el tipo y tamaño del archivo, y los campos requeridos.
3. **MongoDB / GridFS:** almacena los bytes de las imágenes y sus metadatos de captura.
4. **MongoDB y Neo4j:** continúan gestionando, respectivamente, datos de aplicación y relaciones clínicas/conocimiento según el diseño existente.
5. **Capa FHIR en FastAPI:** expone recursos y operaciones normalizadas, sin obligar a que la base de datos interna tenga el mismo esquema.
6. **Sistema externo:** intercambia recursos FHIR mediante HTTPS, autenticación, perfiles y acuerdos de datos previamente definidos.

## 5. Ejemplo ilustrativo de Observation

El siguiente ejemplo es **didáctico** y no representa datos de un paciente real. En una implementación real debe validarse contra la versión FHIR y los perfiles que acuerden los sistemas participantes.

```json
{
  "resourceType": "Observation",
  "status": "final",
  "category": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/CodeSystem/observation-category",
          "code": "vital-signs",
          "display": "Vital Signs"
        }
      ]
    }
  ],
  "code": {
    "text": "Frecuencia cardíaca"
  },
  "subject": {
    "reference": "Patient/PACIENTE-DEMO-001"
  },
  "effectiveDateTime": "2026-10-27T10:00:00Z",
  "valueQuantity": {
    "value": 72,
    "unit": "beats/minute",
    "system": "http://unitsofmeasure.org",
    "code": "/min"
  }
}
```

Este ejemplo demuestra la forma del recurso, no una integración ya implementada. En un intercambio real deben verificarse el identificador de paciente, los códigos clínicos requeridos, la unidad, la hora, la procedencia y el perfil del receptor.

## 6. Primera migración recomendada

La migración debe ser incremental, sin reemplazar de golpe los endpoints existentes.

### Fase A — Definir contrato
- Elegir versión FHIR y perfil de implementación junto al sistema receptor.
- Determinar qué datos de Meditrust ya existen de forma estructurada.
- Definir cómo se mapearán los identificadores internos a referencias FHIR.
- Documentar campos obligatorios, códigos, unidades y errores.

### Fase B — Prototipo de lectura
- Añadir un endpoint de prueba como `GET /fhir/metadata` o, si se implementa un servidor FHIR conforme, `GET /fhir/Patient/{id}`.
- Devolver un recurso validado a partir de datos sintéticos.
- Probar la estructura JSON y los códigos HTTP.
- No declarar conformidad FHIR solo por devolver JSON con un campo `resourceType`.

### Fase C — Prototipo de escritura
- Implementar `POST /fhir/Observation` o un endpoint de entrada que reciba una Observation.
- Validar el recurso y su perfil antes de almacenarlo.
- Registrar procedencia, fecha y usuario responsable.
- Rechazar recursos inválidos con mensajes de error útiles.

### Fase D — Interoperabilidad real
- Configurar HTTPS, autenticación y autorización apropiadas (por ejemplo, OAuth 2.0 según el entorno).
- Acordar los perfiles y terminologías con el sistema externo.
- Realizar pruebas de conformidad y de intercambio extremo a extremo.
- Mantener auditoría y políticas de retención y acceso.

## 7. Relación con la captura de imágenes del smartwatch

La captura de imágenes constituye una entrada de datos, no una medición clínica estructurada. En la primera versión se guardan la imagen, el identificador de paciente indicado, el usuario que la subió, la fecha, el tipo de archivo y el tamaño.

Un desarrollo posterior podría:
1. extraer valores mediante OCR o visión;
2. presentar al personal sanitario los valores detectados y la imagen de origen;
3. exigir confirmación humana cuando corresponda;
4. transformar los valores confirmados a recursos `Observation`;
5. exponer esos recursos a través de una API FHIR validada.

No se debe diagnosticar ni tomar decisiones clínicas a partir de una extracción no verificada.

## 8. Seguridad, privacidad y operación

- Utilizar exclusivamente datos sintéticos en las demostraciones iniciales.
- Exigir autenticación y aplicar autorización por paciente/rol.
- Validar el contenido real del archivo, no confiar únicamente en su extensión o MIME declarado.
- Limitar cantidad y tamaño de archivos.
- Guardar archivos en almacenamiento adecuado y no exponer rutas internas ni enlaces públicos.
- Configurar TLS, secretos en variables de entorno, auditoría y políticas de eliminación/retención antes de tratar datos reales.
- Definir quién puede leer, descargar, corregir o eliminar una captura.
- Evitar que logs y mensajes de error revelen información clínica.

La implementación actual propuesta para la rama de desarrollo es una prueba técnica y no debe considerarse un sistema listo para producción clínica ni para datos reales.

## 9. Plan de pruebas

1. Rechazar una petición sin autenticación.
2. Rechazar identificador de paciente vacío.
3. Rechazar más de cinco archivos.
4. Rechazar un archivo de más de 8 MB.
5. Rechazar archivos que no sean imágenes JPEG, PNG o WEBP válidas.
6. Aceptar una imagen válida y verificar que el registro de metadatos está asociado al ID de prueba.
7. Verificar que las capturas de un usuario no se muestran a otro usuario.
8. Validar los recursos FHIR contra la versión y el perfil acordados antes de conectar sistemas externos.

## 10. Referencias

1. HL7 International. *FHIR Specification*. https://hl7.org/fhir/
2. HL7 International. *Patient — FHIR Resource*. https://hl7.org/fhir/patient.html
3. HL7 International. *Observation — FHIR Resource*. https://hl7.org/fhir/observation.html
4. HL7 International. *Device — FHIR Resource*. https://hl7.org/fhir/device.html
5. HL7 International. *DocumentReference — FHIR Resource*. https://hl7.org/fhir/documentreference.html
6. HL7 International. *RESTful API*. https://hl7.org/fhir/http.html
7. FastAPI. *Request Files*. https://fastapi.tiangolo.com/tutorial/request-files/
8. MongoDB. *GridFS*. https://www.mongodb.com/docs/manual/core/gridfs/
9. OWASP Foundation. *File Upload Cheat Sheet*. https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

**Fecha de consulta de referencias web:** 27 de octubre de 2026.
