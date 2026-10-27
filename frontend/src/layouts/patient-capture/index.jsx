import React, { useEffect, useRef, useState } from "react";
import {
  Alert, Card, CardContent, Chip, CircularProgress, Divider, Grid,
  IconButton, Stack, TextField, Typography, Button,
} from "@mui/material";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

const API_BASE = import.meta.env.VITE_AI_API_URL || "http://127.0.0.1:8000";
const MAX_FILES = 5;
const MAX_FILE_BYTES = 8 * 1024 * 1024;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

export default function PatientCapture() {
  const inputRef = useRef(null);
  const filesRef = useRef([]);
  const [patientId, setPatientId] = useState("");
  const [patientName, setPatientName] = useState("");
  const [notes, setNotes] = useState("");
  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploaded, setUploaded] = useState([]);

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  useEffect(() => () => {
    filesRef.current.forEach((item) => URL.revokeObjectURL(item.preview));
  }, []);

  const addFiles = (event) => {
    const incoming = Array.from(event.target.files || []);
    setError("");
    setMessage(null);

    if (files.length + incoming.length > MAX_FILES) {
      setError("Puedes enviar un máximo de 5 imágenes por operación.");
      event.target.value = "";
      return;
    }

    const invalidType = incoming.find((file) => !ACCEPTED_TYPES.includes(file.type));
    if (invalidType) {
      setError("Formato no admitido. Utiliza imágenes JPG, PNG o WEBP.");
      event.target.value = "";
      return;
    }

    const tooLarge = incoming.find((file) => file.size > MAX_FILE_BYTES);
    if (tooLarge) {
      setError("Cada imagen debe pesar como máximo 8 MB.");
      event.target.value = "";
      return;
    }

    setFiles((previous) => [
      ...previous,
      ...incoming.map((file) => ({ file, preview: URL.createObjectURL(file) })),
    ]);
    event.target.value = "";
  };

  const removeFile = (index) => {
    setFiles((previous) => previous.filter((_, i) => i !== index));
  };

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setMessage(null);
    setUploaded([]);

    if (!patientId.trim()) {
      setError("Introduce un identificador de paciente de prueba.");
      return;
    }
    if (!files.length) {
      setError("Selecciona al menos una imagen.");
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      setError("Tu sesión no contiene un token. Cierra sesión e inicia sesión de nuevo.");
      return;
    }

    const formData = new FormData();
    formData.append("patient_id", patientId.trim());
    formData.append("patient_name", patientName.trim());
    formData.append("notes", notes.trim());
    files.forEach((item) => formData.append("files", item.file));

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/patient-captures/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || `La API respondió con el estado ${response.status}.`);
      }
      setUploaded(body.captures || []);
      setMessage(body.message || "Imágenes enviadas correctamente.");
      setFiles([]);
      setNotes("");
    } catch (err) {
      setError(err.message || "No se pudo conectar con el backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <div style={{ padding: "32px 0" }}>
        <Grid container spacing={3} justifyContent="center">
          <Grid item xs={12} lg={9}>
            <Card>
              <CardContent sx={{ p: { xs: 2, md: 4 } }}>
                <Stack direction="row" spacing={1.5} alignItems="center" mb={1}>
                  <CloudUploadOutlinedIcon color="primary" fontSize="large" />
                  <div>
                    <Typography variant="h5" fontWeight={600}>Captura de datos del paciente</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Adjunta imágenes del smartwatch como si compartieras fotos en un chat.
                    </Typography>
                  </div>
                </Stack>
                <Divider sx={{ my: 3 }} />

                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}

                <form onSubmit={submit}>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <TextField
                        label="Identificador del paciente (obligatorio)"
                        value={patientId}
                        onChange={(e) => setPatientId(e.target.value)}
                        fullWidth required inputProps={{ maxLength: 100 }}
                        helperText="Para la prueba utiliza un ID ficticio, por ejemplo PACIENTE-DEMO-001."
                      />
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <TextField
                        label="Nombre o alias (opcional)"
                        value={patientName}
                        onChange={(e) => setPatientName(e.target.value)}
                        fullWidth inputProps={{ maxLength: 120 }}
                        helperText="Evita introducir datos identificables reales en la demostración."
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        label="Nota de la captura (opcional)"
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        fullWidth multiline minRows={2} inputProps={{ maxLength: 1000 }}
                      />
                    </Grid>
                  </Grid>

                  <input
                    ref={inputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple
                    hidden
                    onChange={addFiles}
                  />

                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<CloudUploadOutlinedIcon />}
                    onClick={() => inputRef.current?.click()}
                    sx={{ mt: 3, py: 2, borderStyle: "dashed", borderWidth: 2 }}
                  >
                    Seleccionar imágenes desde el móvil o el ordenador
                  </Button>
                  <Stack direction="row" spacing={1} alignItems="center" mt={1}>
                    <ImageOutlinedIcon fontSize="small" color="action" />
                    <Typography variant="caption" color="text.secondary">
                      JPG, PNG o WEBP · Hasta 5 imágenes · Máximo 8 MB por imagen
                    </Typography>
                  </Stack>

                  {files.length > 0 && (
                    <Grid container spacing={2} sx={{ mt: 1 }}>
                      {files.map((item, index) => (
                        <Grid item xs={6} sm={4} md={3} key={`${item.file.name}-${item.file.lastModified}-${index}`}>
                          <Card variant="outlined">
                            <img
                              src={item.preview}
                              alt={item.file.name}
                              style={{ width: "100%", height: 130, objectFit: "cover", display: "block" }}
                            />
                            <CardContent sx={{ p: 1.5 }}>
                              <Typography variant="caption" noWrap display="block" title={item.file.name}>
                                {item.file.name}
                              </Typography>
                              <Chip size="small" label={`${(item.file.size / 1024 / 1024).toFixed(2)} MB`} sx={{ mt: 1 }} />
                              <IconButton aria-label="Eliminar imagen" color="error" size="small" onClick={() => removeFile(index)} sx={{ float: "right" }}>
                                <DeleteOutlineIcon fontSize="small" />
                              </IconButton>
                            </CardContent>
                          </Card>
                        </Grid>
                      ))}
                    </Grid>
                  )}

                  <Button
                    type="submit"
                    variant="contained"
                    fullWidth
                    disabled={loading}
                    startIcon={loading ? <CircularProgress size={18} color="inherit" /> : <CloudUploadOutlinedIcon />}
                    sx={{ mt: 3, py: 1.5 }}
                  >
                    {loading ? "Enviando imágenes..." : `Enviar ${files.length || ""} imagen(es)`}
                  </Button>
                </form>

                {uploaded.length > 0 && (
                  <Alert severity="info" sx={{ mt: 3 }}>
                    <Typography variant="subtitle2">Capturas registradas</Typography>
                    {uploaded.map((item) => (
                      <Typography variant="body2" key={item.id}>
                        {item.filename} — {(item.size_bytes / 1024).toFixed(0)} KB
                      </Typography>
                    ))}
                    <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                      Las imágenes se guardaron en MongoDB GridFS y los metadatos quedaron asociados al identificador indicado.
                    </Typography>
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </div>
      <Footer />
    </DashboardLayout>
  );
}
