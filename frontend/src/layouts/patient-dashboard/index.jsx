import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Card, CardContent, CircularProgress, Grid, Stack, TextField, Typography } from "@mui/material";
import LinkOutlinedIcon from "@mui/icons-material/LinkOutlined";
import RefreshOutlinedIcon from "@mui/icons-material/Refresh";
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

export default function PatientDashboard() {
  const [code, setCode] = useState("");
  const [pregnancy, setPregnancy] = useState(null);
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [pregnancyData, relationshipData] = await Promise.all([
        api("/patient/pregnancy"),
        api("/patient/relationships"),
      ]);
      setPregnancy(pregnancyData.pregnancy || null);
      setDoctors(relationshipData.doctors || []);
    } catch (err) { setError(err.message || "No se pudo cargar tu información."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const redeemCode = async (event) => {
    event.preventDefault();
    if (!code.trim()) { setError("Introduce el código que te entregó tu médico."); return; }
    setSubmitting(true); setError(""); setNotice("");
    try {
      const result = await api("/patient/link", { method: "POST", body: JSON.stringify({ code: code.trim() }) });
      setNotice(result.message || "Vinculación completada.");
      setCode("");
      await loadData();
    } catch (err) { setError(err.message); }
    finally { setSubmitting(false); }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <Box py={3}>
        <Typography variant="h4" fontWeight={700}>Mi embarazo</Typography>
        <Typography color="text.secondary" mb={3}>Consulta la información registrada por tu equipo médico y vincula tu cuenta.</Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}

        {loading ? <Box display="flex" justifyContent="center" py={5}><CircularProgress /></Box> : (
          <Grid container spacing={2}>
            <Grid item xs={12} md={7}>
              <Card variant="outlined" sx={{ height: "100%" }}>
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h6" fontWeight={700}>Datos del embarazo</Typography>
                    <Button size="small" startIcon={<RefreshOutlinedIcon />} onClick={loadData}>Actualizar</Button>
                  </Stack>
                  {pregnancy ? (
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="body2" color="text.secondary">Semana gestacional</Typography>
                        <Typography variant="h4" fontWeight={700}>{pregnancy.gestational_week}</Typography>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="body2" color="text.secondary">Fecha probable de parto</Typography>
                        <Typography variant="h6" fontWeight={700}>{pregnancy.due_date ? new Date(`${pregnancy.due_date}T00:00:00`).toLocaleDateString() : "No registrada"}</Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Typography variant="caption" color="text.secondary">
                          {pregnancy.updated_at ? `Última actualización: ${new Date(pregnancy.updated_at).toLocaleString()}` : ""}
                        </Typography>
                      </Grid>
                    </Grid>
                  ) : (
                    <Alert severity="info">Tu médico todavía no ha registrado la fecha probable de parto ni la semana gestacional.</Alert>
                  )}
                  <Typography variant="caption" color="text.secondary" display="block" mt={2}>Estos datos son informativos y solo pueden ser actualizados por un médico vinculado.</Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={5}>
              <Card variant="outlined" sx={{ height: "100%" }}>
                <CardContent>
                  <Typography variant="h6" fontWeight={700} mb={1}>Vincular con un médico</Typography>
                  <Typography variant="body2" color="text.secondary" mb={2}>Introduce el código de un solo uso que te proporcionó tu médico. El código vence en 48 horas.</Typography>
                  <Box component="form" onSubmit={redeemCode}>
                    <TextField fullWidth label="Código de vinculación" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} inputProps={{ maxLength: 24 }} />
                    <Button fullWidth type="submit" variant="contained" startIcon={<LinkOutlinedIcon />} disabled={submitting} sx={{ mt: 2 }}>
                      {submitting ? "Vinculando..." : "Vincular cuenta"}
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" fontWeight={700} mb={2}>Mis médicos vinculados</Typography>
                  {doctors.length ? doctors.map((doctor) => (
                    <Box key={doctor.id} sx={{ py: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
                      <Typography fontWeight={600}>{doctor.name || "Médico"}</Typography>
                      <Typography variant="body2" color="text.secondary">{doctor.email}</Typography>
                    </Box>
                  )) : <Typography variant="body2" color="text.secondary">Todavía no tienes médicos vinculados.</Typography>}
                </CardContent>
              </Card>
            </Grid>

          </Grid>
        )}
      </Box>
      <Footer />
    </DashboardLayout>
  );
}
