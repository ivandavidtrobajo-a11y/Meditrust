import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip,
  CircularProgress, Divider, Grid, MenuItem, Paper, Stack, TextField, Typography,
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";

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

const statusText = {
  queued: "En cola", processing: "En análisis", retrying: "Reintentando",
  no_alerts_detected: "Sin alertas detectadas", needs_review: "Revisión clínica",
  analysis_failed: "Análisis fallido", reviewed: "Revisada",
};
const readingFields = [
  { key: "systolic_bp", label: "Presión sistólica", unit: "mmHg" },
  { key: "diastolic_bp", label: "Presión diastólica", unit: "mmHg" },
  { key: "heart_rate", label: "Frecuencia cardíaca", unit: "lpm" },
  { key: "spo2", label: "Saturación de oxígeno", unit: "%" },
];
const displayValue = (value) => value === null || value === undefined || value === "" ? "No detectado" : String(value);

function ReadingsGrid({ readings = {}, compact = false }) {
  return (
    <Grid container spacing={1}>
      {readingFields.map((field) => (
        <Grid item xs={6} md={compact ? 3 : 6} key={field.key}>
          <Paper variant="outlined" sx={{ p: 1.25, height: "100%" }}>
            <Typography variant="caption" color="text.secondary">{field.label}</Typography>
            <Typography variant={compact ? "subtitle1" : "h6"} fontWeight={700}>
              {displayValue(readings[field.key])}{readings[field.key] !== null && readings[field.key] !== undefined && readings[field.key] !== "" ? ` ${field.unit}` : ""}
            </Typography>
          </Paper>
        </Grid>
      ))}
      {readings.measurement_time && (
        <Grid item xs={12}>
          <Typography variant="caption" color="text.secondary">Hora de medición: {new Date(readings.measurement_time).toLocaleString()}</Typography>
        </Grid>
      )}
    </Grid>
  );
}

function Reviews({ patientId, gridfsId }) {
  const [reviews, setReviews] = useState([]);
  useEffect(() => {
    api(`/patient-captures/${encodeURIComponent(patientId)}/analysis-history?gridfs_id=${encodeURIComponent(gridfsId)}`)
      .then((result) => setReviews(result.reviews || []))
      .catch(() => setReviews([]));
  }, [patientId, gridfsId]);
  if (!reviews.length) return <Typography variant="body2" color="text.secondary">Todavía no hay revisiones médicas registradas.</Typography>;
  return (
    <Stack spacing={1}>
      {reviews.map((review) => (
        <Paper key={review._id} variant="outlined" sx={{ p: 1.5 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1} mb={1}>
            <Typography variant="caption" color="text.secondary">
              {review.reviewed_at ? new Date(review.reviewed_at).toLocaleString() : "Fecha desconocida"}
            </Typography>
            <Chip size="small" color="success" label="Revisión guardada" />
          </Stack>
          <ReadingsGrid readings={review.corrected_readings || {}} compact />
          {review.note && <Typography variant="body2" sx={{ mt: 1 }}>{review.note}</Typography>}
        </Paper>
      ))}
    </Stack>
  );
}

export default function CaptureAnalysisPanel({ patientId, capture, onCaptureUpdated }) {
  const [models, setModels] = useState([]);
  const [selected, setSelected] = useState("");
  const [runs, setRuns] = useState([]);
  const [captureStatus, setCaptureStatus] = useState(capture.analysis_status || "");
  const [loading, setLoading] = useState(false);
  const refreshInFlightRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [corrected, setCorrected] = useState({});
  const [note, setNote] = useState("");

  const selectedModel = useMemo(() => models.find((item) => `${item.provider}:${item.id}` === selected), [models, selected]);

  const refresh = useCallback(async () => {
    if (refreshInFlightRef.current) return;
    refreshInFlightRef.current = true;
    setLoading(true);
    try {
      const [result, captureResult] = await Promise.all([
        api(`/patient-captures/${encodeURIComponent(patientId)}/analysis-history?gridfs_id=${encodeURIComponent(capture.gridfs_id)}`),
        api(`/patient-captures/${encodeURIComponent(patientId)}`),
      ]);
      setRuns(result.runs || []);
      const currentCapture = (captureResult.captures || []).find((item) => item.gridfs_id === capture.gridfs_id);
      if (currentCapture) {
        setCaptureStatus(currentCapture.analysis_status || "");
        onCaptureUpdated?.(patientId, currentCapture);
      }
      const latest = (result.runs || []).find((run) => run.readings);
      if (latest) setCorrected((previous) => Object.keys(previous).length ? previous : { ...latest.readings });
    } catch (err) { setError(err.message); }
    finally { refreshInFlightRef.current = false; setLoading(false); }
  }, [patientId, capture.gridfs_id, onCaptureUpdated]);

  useEffect(() => { setCaptureStatus(capture.analysis_status || ""); }, [capture.analysis_status]);
  const analysisPending = ["queued", "processing", "retrying"].includes(captureStatus);
  useEffect(() => {
    if (!analysisPending) return undefined;
    const interval = window.setInterval(() => { refresh(); }, 4000);
    return () => window.clearInterval(interval);
  }, [analysisPending, refresh]);

  useEffect(() => {
    let active = true;
    api("/doctor/capture-models").then((result) => {
      if (!active) return;
      setModels(result.models || []);
      if (result.models?.length) setSelected((previous) => previous || `${result.models[0].provider}:${result.models[0].id}`);
    }).catch((err) => { if (active) setError(err.message); });
    refresh();
    return () => { active = false; };
  }, [patientId, capture.gridfs_id, refresh]);

  const reanalyze = async () => {
    if (!selectedModel) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/doctor/patient-captures/${encodeURIComponent(patientId)}/${encodeURIComponent(capture.gridfs_id)}/reanalyze`, {
        method: "POST", body: JSON.stringify({ provider: selectedModel.provider, model: selectedModel.id }),
      });
      setCaptureStatus("queued");
      setNotice("Nueva ejecución añadida a la cola. Las ejecuciones anteriores se conservan.");
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const saveReview = async () => {
    if (busy) return;
    if (!patientId || !capture?.gridfs_id) {
      setError("No se pudo identificar la captura que se desea revisar.");
      return;
    }
    const values = { ...corrected };
    readingFields.forEach(({ key }) => {
      const value = values[key];
      if (value === "" || value === undefined) values[key] = null;
      else if (value !== null && Number.isFinite(Number(value))) values[key] = Number(value);
    });
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api(`/doctor/patient-captures/${encodeURIComponent(patientId)}/${encodeURIComponent(capture.gridfs_id)}/review`, {
        method: "PUT", body: JSON.stringify({ corrected_readings: values, note }),
      });
      setCaptureStatus(result.status || "reviewed");
      setNotice("Revisión médica guardada. Los valores corregidos se reflejarán en el historial de la paciente.");
      // El guardado ya fue confirmado por el servidor. La actualización del historial
      // se realiza aparte para que un fallo secundario de consulta no oculte el éxito.
      void refresh();
    } catch (err) {
      setError(err.message || "No se pudo guardar la revisión médica.");
    } finally {
      setBusy(false);
    }
  };

  const updateReading = (key, value) => setCorrected((previous) => ({ ...previous, [key]: value }));

  return (
    <Stack spacing={2} sx={{ mt: 1, p: { xs: 1.25, sm: 2 }, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ xs: "stretch", sm: "center" }} justifyContent="space-between">
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Análisis de la captura</Typography>
          <Typography variant="caption" color="text.secondary">Resultados extraídos y herramientas de revisión médica</Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip size="small" label={statusText[captureStatus] || captureStatus || "Sin analizar"} color={captureStatus === "needs_review" || captureStatus === "analysis_failed" ? "warning" : captureStatus === "reviewed" ? "success" : "default"} />
          <Button size="small" onClick={refresh} disabled={loading}>{loading ? <CircularProgress size={15} /> : "Actualizar"}</Button>
        </Stack>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {notice && <Alert severity="success">{notice}</Alert>}

      <Box>
        <Typography variant="subtitle2" fontWeight={700} mb={1}>Mediciones extraídas por IA</Typography>
        {runs.find((run) => run.readings)?.readings
          ? <ReadingsGrid readings={runs.find((run) => run.readings).readings} />
          : <Typography variant="body2" color="text.secondary">Todavía no hay mediciones disponibles.</Typography>}
        <Alert severity="info" sx={{ mt: 1 }}>
          Los valores son una extracción automática de la imagen y no constituyen un diagnóstico. La ausencia de un valor significa que no pudo identificarse.
        </Alert>
      </Box>

      <Divider />
      <Box>
        <Typography variant="subtitle2" fontWeight={700} mb={1}>Revisión médica</Typography>
        <Typography variant="body2" color="text.secondary" mb={1.5}>
          Confirma o corrige cada medición. Deja vacío un campo si no dispones de un valor fiable.
        </Typography>
        <Grid container spacing={1.5}>
          {readingFields.map((field) => (
            <Grid item xs={12} sm={6} key={field.key}>
              <TextField
                fullWidth size="small" type="number" label={`${field.label} (${field.unit})`}
                value={corrected[field.key] ?? ""}
                onChange={(event) => updateReading(field.key, event.target.value)}
              />
            </Grid>
          ))}
        </Grid>
        <TextField
          fullWidth size="small" sx={{ mt: 1.5 }} label="Fecha y hora de medición (opcional)"
          value={corrected.measurement_time || ""}
          onChange={(event) => updateReading("measurement_time", event.target.value)}
          placeholder="Ej. 2026-11-15T09:30:00"
        />
        <TextField fullWidth size="small" multiline minRows={2} sx={{ mt: 1.5 }}
          value={note} onChange={(event) => setNote(event.target.value)} label="Observaciones médicas" />
        <Button fullWidth variant="contained" disabled={busy} onClick={saveReview} sx={{ mt: 1.5 }}>
          {busy ? "Guardando..." : "Guardar revisión médica"}
        </Button>
      </Box>

      <Divider />
      <Accordion disableGutters elevation={0} variant="outlined">
        <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
          <Typography variant="subtitle2" fontWeight={700}>Historial de revisiones médicas</Typography>
        </AccordionSummary>
        <AccordionDetails><Reviews patientId={patientId} gridfsId={capture.gridfs_id} /></AccordionDetails>
      </Accordion>

      <Accordion disableGutters elevation={0} variant="outlined">
        <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
          <Typography variant="subtitle2" fontWeight={700}>Ejecuciones y respuestas técnicas ({runs.length})</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1.5}>
            {runs.map((run, index) => (
              <Paper key={run._id} variant="outlined" sx={{ p: 1.5 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
                  <Typography variant="body2" fontWeight={700}>Ejecución {runs.length - index}</Typography>
                  <Chip size="small" label={run.status || "Estado desconocido"} color={run.status === "completed" ? "success" : run.status === "failed" ? "error" : "default"} />
                </Stack>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                  {run.provider || "Proveedor desconocido"} / {run.model || "Modelo desconocido"} · {run.started_at ? new Date(run.started_at).toLocaleString() : "Fecha desconocida"}
                </Typography>
                {run.readings && <Box mt={1}><ReadingsGrid readings={run.readings} compact /></Box>}
                {run.review_reasons?.map((reason, reasonIndex) => <Typography key={reasonIndex} variant="caption" color="warning.main" display="block">{reason}</Typography>)}
                {run.error && <Alert severity="error" sx={{ mt: 1 }}>{run.error}</Alert>}
                {run.raw_response && (
                  <details style={{ marginTop: 10 }}>
                    <summary>Ver respuesta original del proveedor</summary>
                    <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 11 }}>{JSON.stringify(run.raw_response, null, 2)}</pre>
                  </details>
                )}
              </Paper>
            ))}
            {models.length > 0 ? (
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                <TextField select size="small" fullWidth label="Modelo para nuevo análisis" value={selected} onChange={(event) => setSelected(event.target.value)}>
                  {models.map((model) => <MenuItem key={model.provider + ":" + model.id} value={`${model.provider}:${model.id}`}>{model.name || model.id} · {model.provider}</MenuItem>)}
                </TextField>
                <Button variant="outlined" disabled={busy || !selectedModel} onClick={reanalyze}>Reanalizar</Button>
              </Stack>
            ) : <Typography variant="caption" color="text.secondary">No hay modelos multimodales configurados para análisis manual.</Typography>}
          </Stack>
        </AccordionDetails>
      </Accordion>
    </Stack>
  );
}
