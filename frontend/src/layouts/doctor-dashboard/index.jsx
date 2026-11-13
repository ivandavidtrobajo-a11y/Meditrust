import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress,
  Grid, Stack, TextField, Typography,
} from "@mui/material";
import ContentCopyOutlinedIcon from "@mui/icons-material/ContentCopyOutlined";
import PersonAddAlt1OutlinedIcon from "@mui/icons-material/PersonAddAlt1Outlined";
import RefreshOutlinedIcon from "@mui/icons-material/Refresh";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import CaptureAnalysisPanel from "layouts/doctor-dashboard/CaptureAnalysisPanel";
import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

const API_BASE = import.meta.env.VITE_AI_API_URL || "http://127.0.0.1:8000";
const authHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("token") || ""}` });

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...authHeaders(), "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || body.message || `Error HTTP ${response.status}`);
  return body;
}

export default function DoctorDashboard() {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [generatedCode, setGeneratedCode] = useState(null);
  const [forms, setForms] = useState({});
  const [capturesByPatient, setCapturesByPatient] = useState({});
  const [captureLoading, setCaptureLoading] = useState("");
  const [captureImageUrls, setCaptureImageUrls] = useState({});
  const [captureImageLoading, setCaptureImageLoading] = useState("");
  const captureImageUrlsRef = useRef({});

  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api("/doctor/patients");
      setPatients(data.patients || []);
      setForms(Object.fromEntries((data.patients || []).map((p) => [p.patient_id, {
        due_date: p.pregnancy?.due_date || "",
        gestational_week: p.pregnancy?.gestational_week ?? "",
      }])));
    } catch (err) {
      setError(err.message || "No se pudo cargar la lista de pacientes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPatients(); }, [loadPatients]);

  const createCode = async () => {
    setBusy(true); setError(""); setNotice(""); setGeneratedCode(null);
    try {
      const result = await api("/doctor/linking-codes", { method: "POST" });
      setGeneratedCode(result);
      setNotice("Código creado. Compártelo con la paciente; solo puede utilizarse una vez.");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const updateField = (patientId, field, value) => {
    setForms((previous) => ({
      ...previous,
      [patientId]: { ...(previous[patientId] || {}), [field]: value },
    }));
  };

  const savePregnancy = async (patientId) => {
    const form = forms[patientId] || {};
    if (!form.due_date || form.gestational_week === "" || Number(form.gestational_week) < 0 || Number(form.gestational_week) > 42) {
      setError("Completa la fecha probable de parto y una semana gestacional entre 0 y 42.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/doctor/patients/${encodeURIComponent(patientId)}/pregnancy`, {
        method: "PUT",
        body: JSON.stringify({ due_date: form.due_date, gestational_week: Number(form.gestational_week) }),
      });
      setNotice("Datos del embarazo actualizados.");
      await loadPatients();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const loadCaptures = async (patientId) => {
    setCaptureLoading(patientId); setError("");
    try {
      const data = await api(`/patient-captures/${encodeURIComponent(patientId)}`);
      setCapturesByPatient((previous) => ({ ...previous, [patientId]: data.captures || [] }));
    } catch (err) { setError(err.message || "No se pudieron consultar las capturas."); }
    finally { setCaptureLoading(""); }
  };

  const toggleCaptureImage = async (capture) => {
    const imageId = capture.gridfs_id;
    if (captureImageUrls[imageId]) {
      URL.revokeObjectURL(captureImageUrls[imageId]);
      setCaptureImageUrls((previous) => {
        const next = { ...previous };
        delete next[imageId];
        return next;
      });
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      setError("Tu sesión no contiene un token. Inicia sesión de nuevo.");
      return;
    }

    setError("");
    setCaptureImageLoading(imageId);
    try {
      const url = `${API_BASE}/patient-captures/${encodeURIComponent(capture.patient_id)}/${encodeURIComponent(imageId)}/image`;
      const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `No se pudo recuperar la imagen (HTTP ${response.status}).`);
      }
      const objectUrl = URL.createObjectURL(await response.blob());
      setCaptureImageUrls((previous) => {
        if (previous[imageId]) URL.revokeObjectURL(previous[imageId]);
        return { ...previous, [imageId]: objectUrl };
      });
    } catch (err) {
      setError(err.message || "No se pudo recuperar la imagen original.");
    } finally {
      setCaptureImageLoading("");
    }
  };

  useEffect(() => {
    captureImageUrlsRef.current = captureImageUrls;
  }, [captureImageUrls]);

  useEffect(() => () => {
    Object.values(captureImageUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const deactivate = async (patientId) => {
    if (!window.confirm("¿Desactivar la vinculación con esta paciente? El historial se conservará.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/doctor/patients/${encodeURIComponent(patientId)}/assignment`, { method: "DELETE" });
      setNotice("Vinculación desactivada. El historial se conserva.");
      await loadPatients();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const copyCode = async () => {
    if (!generatedCode?.code) return;
    try { await navigator.clipboard.writeText(generatedCode.code); setNotice("Código copiado."); }
    catch { setNotice("No se pudo copiar automáticamente. Selecciona el código y cópialo."); }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <Box py={3}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "stretch", sm: "center" }} spacing={2} mb={3}>
          <Box>
            <Typography variant="h4" fontWeight={700}>Panel médico</Typography>
            <Typography color="text.secondary">Gestiona las vinculaciones y los datos del embarazo de tus pacientes.</Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Button variant="outlined" startIcon={<RefreshOutlinedIcon />} onClick={loadPatients}>Actualizar</Button>
            <Button variant="contained" startIcon={<PersonAddAlt1OutlinedIcon />} onClick={createCode} disabled={busy}>Generar código</Button>
          </Stack>
        </Stack>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}

        {generatedCode && (
          <Card variant="outlined" sx={{ mb: 3, borderColor: "primary.main" }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={700}>Código de vinculación</Typography>
              <Typography variant="body2" color="text.secondary" mb={1}>Entrégalo a la paciente para que lo introduzca en su cuenta. Es de un solo uso y vence en 48 horas.</Typography>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ xs: "stretch", sm: "center" }}>
                <Typography variant="h4" fontWeight={700} letterSpacing={3}>{generatedCode.code}</Typography>
                <Button variant="outlined" startIcon={<ContentCopyOutlinedIcon />} onClick={copyCode}>Copiar código</Button>
              </Stack>
              <Typography variant="caption" color="text.secondary">Vence: {new Date(generatedCode.expires_at).toLocaleString()}</Typography>
            </CardContent>
          </Card>
        )}

        <Stack direction="row" alignItems="center" spacing={1} mb={2}>
          <Typography variant="h5" fontWeight={700}>Mis pacientes</Typography>
          <Chip label={patients.length} color="primary" size="small" />
        </Stack>

        {loading ? <Box display="flex" justifyContent="center" py={5}><CircularProgress /></Box> :
          patients.length === 0 ? (
            <Card variant="outlined"><CardContent>
              <Typography fontWeight={600}>Todavía no tienes pacientes vinculadas.</Typography>
              <Typography color="text.secondary" variant="body2">Genera un código y compártelo con la paciente para crear la vinculación.</Typography>
            </CardContent></Card>
          ) : (
            <Grid container spacing={2}>
              {patients.map((patient) => {
                const form = forms[patient.patient_id] || {};
                return (
                  <Grid item xs={12} md={6} key={patient.patient_id}>
                    <Card variant="outlined" sx={{ height: "100%" }}>
                      <CardContent>
                        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
                          <Box>
                            <Typography variant="h6" fontWeight={700}>{patient.name || "Paciente"}</Typography>
                            <Typography variant="body2" color="text.secondary">{patient.email}</Typography>
                          </Box>
                          <Chip label="Vinculación activa" color="success" size="small" />
                        </Stack>
                        <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                          Vinculada desde {new Date(patient.assigned_at).toLocaleDateString()}
                        </Typography>
                        <Typography variant="subtitle2" mt={2} mb={1}>Datos del embarazo</Typography>
                        <Grid container spacing={1.5}>
                          <Grid item xs={12} sm={7}>
                            <TextField fullWidth size="small" type="date" label="Fecha probable de parto"
                              InputLabelProps={{ shrink: true }} value={form.due_date || ""}
                              onChange={(e) => updateField(patient.patient_id, "due_date", e.target.value)} />
                          </Grid>
                          <Grid item xs={12} sm={5}>
                            <TextField fullWidth size="small" type="number" label="Semana gestacional"
                              inputProps={{ min: 0, max: 42 }} value={form.gestational_week ?? ""}
                              onChange={(e) => updateField(patient.patient_id, "gestational_week", e.target.value)} />
                          </Grid>
                        </Grid>
                        <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                          {patient.pregnancy?.updated_at ? `Última actualización: ${new Date(patient.pregnancy.updated_at).toLocaleString()}` : "Aún no se han registrado datos del embarazo."}
                        </Typography>
                        <Stack direction={{ xs: "column", sm: "row" }} spacing={1} mt={2}>
                          <Button fullWidth variant="contained" disabled={busy} onClick={() => savePregnancy(patient.patient_id)}>Guardar embarazo</Button>
                          <Button fullWidth color="error" variant="outlined" disabled={busy} onClick={() => deactivate(patient.patient_id)}>Desvincular</Button>
                        </Stack>
                        <Button fullWidth sx={{ mt: 1 }} variant="outlined" startIcon={<ImageOutlinedIcon />}
                          disabled={captureLoading === patient.patient_id}
                          onClick={() => loadCaptures(patient.patient_id)}>
                          {captureLoading === patient.patient_id ? "Consultando capturas..." : "Consultar capturas y experimentos"}
                        </Button>
                        {capturesByPatient[patient.patient_id] && (
                          <Box mt={1} sx={{ maxHeight: 220, overflowY: "auto" }}>
                            {capturesByPatient[patient.patient_id].length ? capturesByPatient[patient.patient_id].map((capture) => (
                              <Box key={capture.gridfs_id} py={1} sx={{ borderBottom: "1px solid", borderColor: "divider" }}>
                                <Typography variant="body2" fontWeight={600} sx={{ overflowWrap: "anywhere" }}>
                                  {capture.original_filename || "Captura sin nombre"}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" display="block">
                                  {capture.uploaded_at ? new Date(capture.uploaded_at).toLocaleString() : "Fecha no disponible"}
                                  {capture.size_bytes ? ` · ${Math.round(capture.size_bytes / 1024)} KB` : ""}
                                </Typography>
                                {capture.notes && <Typography variant="caption" display="block">{capture.notes}</Typography>}
                                <CaptureAnalysisPanel patientId={patient.patient_id} capture={capture} />
                                {captureImageUrls[capture.gridfs_id] && (
                                  <Box mt={1}>
                                    <img
                                      src={captureImageUrls[capture.gridfs_id]}
                                      alt={capture.original_filename || "Captura del smartwatch"}
                                      style={{ width: "100%", maxHeight: 260, objectFit: "contain", display: "block", background: "#f5f5f5", borderRadius: 8 }}
                                    />
                                  </Box>
                                )}
                                <Button
                                  fullWidth
                                  size="small"
                                  sx={{ mt: 1 }}
                                  variant={captureImageUrls[capture.gridfs_id] ? "text" : "outlined"}
                                  disabled={captureImageLoading === capture.gridfs_id}
                                  onClick={() => toggleCaptureImage(capture)}
                                  startIcon={captureImageLoading === capture.gridfs_id ? <CircularProgress size={16} /> : <ImageOutlinedIcon />}
                                >
                                  {captureImageLoading === capture.gridfs_id ? "Cargando imagen..." : captureImageUrls[capture.gridfs_id] ? "Ocultar imagen" : "Ver imagen original"}
                                </Button>
                              </Box>
                            )) : <Typography variant="body2" color="text.secondary">Esta paciente todavía no ha subido capturas.</Typography>}
                          </Box>
                        )}
                      </CardContent>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          )}
      </Box>
      <Footer />
    </DashboardLayout>
  );
}
