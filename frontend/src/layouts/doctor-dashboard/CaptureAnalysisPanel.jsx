import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Chip, CircularProgress, Divider, MenuItem, Stack, TextField, Typography } from "@mui/material";

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
  queued: "En cola", processing: "En análisis", retrying: "Reintentando", no_alerts_detected: "Sin alertas detectadas",
  needs_review: "Revisión clínica", analysis_failed: "Análisis fallido", reviewed: "Revisada",
};

function Reviews({ patientId, gridfsId }) {
  const [reviews, setReviews] = useState([]);
  useEffect(() => {
    api(`/patient-captures/${encodeURIComponent(patientId)}/analysis-history?gridfs_id=${encodeURIComponent(gridfsId)}`)
      .then((result) => setReviews(result.reviews || []))
      .catch(() => setReviews([]));
  }, [patientId, gridfsId]);
  return reviews.map((review) => (
    <Stack key={review._id} spacing={0.25}>
      <Typography variant="caption" color="text.secondary">{review.reviewed_at ? new Date(review.reviewed_at).toLocaleString() : "Fecha desconocida"}</Typography>
      <Typography variant="body2">Corrección: {JSON.stringify(review.corrected_readings)}</Typography>
      {review.note && <Typography variant="caption">{review.note}</Typography>}
    </Stack>
  ));
}

export default function CaptureAnalysisPanel({ patientId, capture }) {
  const [models, setModels] = useState([]);
  const [selected, setSelected] = useState("");
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [corrected, setCorrected] = useState("{}");
  const [note, setNote] = useState("");

  const selectedModel = useMemo(() => models.find((item) => `${item.provider}:${item.id}` === selected), [models, selected]);

  const refresh = async () => {
    setLoading(true);
    try {
      const result = await api(`/patient-captures/${encodeURIComponent(patientId)}/analysis-history?gridfs_id=${encodeURIComponent(capture.gridfs_id)}`);
      setRuns(result.runs || []);
      const latest = (result.runs || []).find((run) => run.readings);
      if (latest) setCorrected(JSON.stringify(latest.readings, null, 2));
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    let active = true;
    api("/doctor/capture-models").then((result) => {
      if (!active) return;
      setModels(result.models || []);
      if (result.models?.length) setSelected((previous) => previous || `${result.models[0].provider}:${result.models[0].id}`);
    }).catch((err) => { if (active) setError(err.message); });
    refresh();
    return () => { active = false; };
  }, [patientId, capture.gridfs_id]);

  const reanalyze = async () => {
    if (!selectedModel) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/doctor/patient-captures/${encodeURIComponent(patientId)}/${encodeURIComponent(capture.gridfs_id)}/reanalyze`, {
        method: "POST", body: JSON.stringify({ provider: selectedModel.provider, model: selectedModel.id }),
      });
      setNotice("Nueva ejecución añadida a la cola. Las ejecuciones anteriores se conservan.");
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const saveReview = async () => {
    let values;
    try { values = JSON.parse(corrected); }
    catch { setError("El JSON de corrección no es válido."); return; }
    if (!values || typeof values !== "object" || Array.isArray(values)) {
      setError("Las correcciones deben ser un objeto JSON.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/doctor/patient-captures/${encodeURIComponent(patientId)}/${encodeURIComponent(capture.gridfs_id)}/review`, {
        method: "PUT", body: JSON.stringify({ corrected_readings: values, note }),
      });
      setNotice("Revisión médica guardada; el resultado original permanece en el historial.");
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return (
    <Stack spacing={1} sx={{ mt: 1, p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
        <Chip size="small" label={statusText[capture.analysis_status] || capture.analysis_status || "Sin analizar"} color={capture.analysis_status === "needs_review" || capture.analysis_status === "analysis_failed" ? "warning" : "default"} />
        <Button size="small" onClick={refresh} disabled={loading}>{loading ? "Actualizando..." : "Actualizar historial"}</Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {notice && <Alert severity="success">{notice}</Alert>}
      {runs.map((run) => (
        <Stack key={run._id} spacing={0.5}>
          <Typography variant="caption" color="text.secondary">
            {run.provider} / {run.model} · {run.started_at ? new Date(run.started_at).toLocaleString() : "Fecha desconocida"} · {run.status}
          </Typography>
          {run.readings && <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(run.readings)}</Typography>}
          {run.review_reasons?.map((reason, index) => <Typography key={index} variant="caption" color="warning.main">{reason}</Typography>)}
          {run.error && <Typography variant="caption" color="error">{run.error}</Typography>}
          {run.raw_response && <details><summary>Respuesta original del proveedor</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 11 }}>{JSON.stringify(run.raw_response, null, 2)}</pre></details>}
          <Divider />
        </Stack>
      ))}
      {models.length > 0 ? (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <TextField select size="small" fullWidth label="Modelo para nuevo análisis" value={selected} onChange={(event) => setSelected(event.target.value)}>
            {models.map((model) => <MenuItem key={model.provider + ":" + model.id} value={`${model.provider}:${model.id}`}>{model.name || model.id} · {model.provider}</MenuItem>)}
          </TextField>
          <Button variant="outlined" disabled={busy || !selectedModel} onClick={reanalyze}>Reanalizar</Button>
        </Stack>
      ) : <Typography variant="caption" color="text.secondary">No hay modelos multimodales configurados para análisis manual.</Typography>}
      <Typography variant="subtitle2">Revisiones médicas anteriores</Typography>
      <Reviews patientId={patientId} gridfsId={capture.gridfs_id} />
      <Typography variant="subtitle2">Corrección médica (JSON)</Typography>
      <TextField multiline minRows={3} value={corrected} onChange={(event) => setCorrected(event.target.value)} placeholder='{"systolic_bp": 120}' />
      <TextField size="small" multiline minRows={2} value={note} onChange={(event) => setNote(event.target.value)} label="Observaciones médicas" />
      <Button variant="contained" disabled={busy} onClick={saveReview}>Guardar revisión</Button>
    </Stack>
  );
}
