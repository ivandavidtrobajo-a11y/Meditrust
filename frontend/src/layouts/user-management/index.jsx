import { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, CircularProgress, Grid,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Typography, Chip, Stack,
} from "@mui/material";
import PersonAddAlt1OutlinedIcon from "@mui/icons-material/PersonAddAlt1Outlined";
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

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api("/admin/users");
      setUsers(result.users || []);
    } catch (err) {
      setError(err.message || "No se pudieron cargar las cuentas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  const createDoctor = async (event) => {
    event.preventDefault();
    setCreating(true);
    setError("");
    setNotice("");
    try {
      const result = await api("/admin/doctors", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setNotice(result.message || "Cuenta médica creada.");
      setForm({ name: "", email: "", password: "" });
      await loadUsers();
    } catch (err) {
      setError(err.message || "No se pudo crear la cuenta médica.");
    } finally {
      setCreating(false);
    }
  };

  const roleLabel = (role) => ({
    admin: "Administrador",
    medico: "Médico",
    embarazada: "Paciente",
  }[role] || role);

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <Box py={3}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "stretch", sm: "center" }} spacing={2} mb={3}>
          <Box>
            <Typography variant="h4" fontWeight={700}>Gestión de usuarios</Typography>
            <Typography color="text.secondary">Consulta las cuentas y habilita el acceso de nuevos médicos.</Typography>
          </Box>
          <Button variant="outlined" startIcon={<RefreshOutlinedIcon />} onClick={loadUsers}>Actualizar lista</Button>
        </Stack>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}

        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" fontWeight={700} mb={1}>Registrar médico</Typography>
                <Typography variant="body2" color="text.secondary" mb={2}>
                  El rol médico se asigna exclusivamente desde esta sección. Comparte la contraseña inicial por un canal seguro.
                </Typography>
                <Box component="form" onSubmit={createDoctor}>
                  <TextField fullWidth required label="Nombre completo" value={form.name}
                    onChange={(e) => setForm((v) => ({ ...v, name: e.target.value }))} inputProps={{ maxLength: 120 }} sx={{ mb: 2 }} />
                  <TextField fullWidth required type="email" label="Correo electrónico" value={form.email}
                    onChange={(e) => setForm((v) => ({ ...v, email: e.target.value }))} sx={{ mb: 2 }} />
                  <TextField fullWidth required type="password" label="Contraseña inicial (mínimo 8 caracteres)" value={form.password}
                    onChange={(e) => setForm((v) => ({ ...v, password: e.target.value }))} inputProps={{ minLength: 8, maxLength: 128 }} sx={{ mb: 2 }} />
                  <Button fullWidth type="submit" variant="contained" startIcon={<PersonAddAlt1OutlinedIcon />} disabled={creating}>
                    {creating ? "Creando cuenta..." : "Crear cuenta médica"}
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={7}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" fontWeight={700} mb={2}>Cuentas registradas</Typography>
                {loading ? <Box display="flex" justifyContent="center" py={4}><CircularProgress /></Box> : (
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Usuario</TableCell>
                          <TableCell>Correo</TableCell>
                          <TableCell>Rol</TableCell>
                          <TableCell>Registro</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {users.map((user) => (
                          <TableRow key={user.id}>
                            <TableCell>{user.name || "Sin nombre"}</TableCell>
                            <TableCell sx={{ overflowWrap: "anywhere" }}>{user.email}</TableCell>
                            <TableCell><Chip size="small" label={roleLabel(user.role)} color={user.role === "admin" ? "secondary" : user.role === "medico" ? "info" : "default"} /></TableCell>
                            <TableCell>{user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}</TableCell>
                          </TableRow>
                        ))}
                        {!users.length && <TableRow><TableCell colSpan={4} align="center">No hay cuentas registradas.</TableCell></TableRow>}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
      <Footer />
    </DashboardLayout>
  );
}
