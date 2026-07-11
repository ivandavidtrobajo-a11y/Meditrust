// Medistrust.js
import { useState, useEffect, useRef } from "react";
import Card from "@mui/material/Card";
import Grid from "@mui/material/Grid";
import Icon from "@mui/material/Icon";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Divider from "@mui/material/Divider";
import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import { useNavigate } from "react-router-dom";
import { useMaterialUIController, setLayout } from "context";
import { Mirage } from "ldrs/react";
import "ldrs/react/Mirage.css";

function Medistrust() {
  const [controller, dispatch] = useMaterialUIController();
  const navigate = useNavigate();

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [history, setHistory] = useState([]);

  const [search, setSearch] = useState("");

  const [loading, setLoading] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState(null);
  const pollIntervalRef = useRef(null);
  const isSendingRef = useRef(false);
  const processedTasksRef = useRef(new Set());

  // Model selector
  const [models, setModels] = useState({ hf: [], ollama: [] });
  const [selectedModel, setSelectedModel] = useState(() => {
    return localStorage.getItem("selectedModel") || "";
  });

  // Fetch available models on mount
  useEffect(() => {
    fetch(`${API_BASE}/models`)
      .then((r) => r.json())
      .then((data) => {
        setModels(data);
        if (!localStorage.getItem("selectedModel")) {
          const allModels = [...(data.hf || []), ...(data.ollama || [])];
          if (allModels.length > 0) {
            setSelectedModel(allModels[0].id);
          }
        }
      })
      .catch(() => console.warn("No se pudo obtener lista de modelos"));
  }, []);

  // Persist selected model
  useEffect(() => {
    if (selectedModel) localStorage.setItem("selectedModel", selectedModel);
  }, [selectedModel]);

  // Documents panel
  const [documents, setDocuments] = useState([]);
  const [showSidebar, setShowSidebar] = useState(false);
  const [docSearch, setDocSearch] = useState("");

  const API_BASE = import.meta.env.VITE_AI_API_URL || "";
  // Layout: full screen (hide menu) while component is mounted
  useEffect(() => {
    setLayout(dispatch, "vr");
    return () => setLayout(dispatch, "dashboard");
  }, [dispatch]);

  // Load history from localStorage
  useEffect(() => {
    const savedHistory = localStorage.getItem("chatHistory");
    if (savedHistory) setHistory(JSON.parse(savedHistory));
  }, []);

  // Persist history to localStorage
  useEffect(() => {
    localStorage.setItem("chatHistory", JSON.stringify(history));
  }, [history]);

  // Cleanup on unmount (clear polling if any)
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, []);

  // Filtered history (search)
  const filteredHistory = history.filter((item) => item.toLowerCase().includes(search.toLowerCase()));

const handleSend = async () => {
  if (!input.trim() || loading || isSendingRef.current) {
    console.log("handleSend bloqueado:", { input: input.trim(), loading, isSending: isSendingRef.current });
    return;
  }
  isSendingRef.current = true;
  console.log("handleSend ejecutado:", input);

  const userQuestion = input;
  setMessages((prev) => [...prev, { text: userQuestion, sender: "user" }]);
  setInput("");
  setLoading(true);

  try {
    // Paso 1: iniciar tarea
    const resp = await fetch(`${API_BASE}/ask/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: userQuestion, model: selectedModel || undefined }),
    });

    if (!resp.ok) {
      const txt = await resp.text();
      console.error("ask/ failed:", resp.status, txt);
      setMessages((prev) => [
        ...prev,
        { text: "Error al iniciar la consulta en el servidor.", sender: "system" },
      ]);
      setLoading(false);
      isSendingRef.current = false;
      return;
    }

    const data = await resp.json();
    const taskId = data.task_id;

    if (!taskId) {
      setMessages((prev) => [...prev, { text: "Error: el servidor no devolvió task_id.", sender: "system" }]);
      setLoading(false);
      isSendingRef.current = false;
      return;
    }

    setCurrentTaskId(taskId);

    // Paso 2: iniciar polling
    pollIntervalRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API_BASE}/result/${taskId}`);
        const task = await r.json();

        if (task.status === "finished" && !processedTasksRef.current.has(taskId)) {
          processedTasksRef.current.add(taskId);
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;

          setMessages((prev) => [...prev, { text: task.answer, sender: "system" }]);

          setHistory((prev) => [
            ...prev,
            `👤 Usuario: ${userQuestion}`,
            `🤖 Medistrust: ${task.answer}`,
          ]);

          setLoading(false);
          setCurrentTaskId(null);
          isSendingRef.current = false;
        }

        if (task.status === "error" && !processedTasksRef.current.has(taskId)) {
          processedTasksRef.current.add(taskId);
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;

          setMessages((prev) => [...prev, { text: "Error en la IA: " + task.error, sender: "system" }]);
          setLoading(false);
          setCurrentTaskId(null);
          isSendingRef.current = false;
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1500);

  } catch (error) {
    console.error("Error en handleSend:", error);
    setMessages((prev) => [
      ...prev,
      { text: "Error al conectar con el servidor.", sender: "system" },
    ]);
    setLoading(false);
    isSendingRef.current = false;
  }
};



  // --------------------------
  //  Detener IA (cancel task on backend)
  // --------------------------
// ... (resto sin cambio)

const handleStopIA = async () => {
  if (!currentTaskId) {
    setMessages((prev) => [...prev, { text: "No hay tarea activa para detener.", sender: "system" }]);
    return;
  }

  try {
    const resp = await fetch(`${API_BASE}/cancel/${currentTaskId}`, { method: "POST" });
    if (resp.ok) {
      setMessages((prev) => [...prev, { text: "Consulta detenida.", sender: "system" }]);
    } else {
      setMessages((prev) => [...prev, { text: "Error al detener IA.", sender: "system" }]);
    }
  } catch (err) {
    console.error("Cancel error:", err);
    setMessages((prev) => [...prev, { text: "Error al conectar para detener.", sender: "system" }]);
  }

  setLoading(false);
  setCurrentTaskId(null);

  if (pollIntervalRef.current) {
    clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = null;
  }
};

// ... (resto sin cambio)

  // --------------------------
  //  File upload
  // --------------------------
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);

    try {
      const resp = await fetch(`${API_BASE}/upload/`, { method: "POST", body: formData });
      const data = await resp.json();
      const msg = data.message || data.detail || `Archivo subido: ${file.name}`;
      setMessages((prev) => [...prev, { text: msg, sender: "system" }]);
      setHistory((prev) => [...prev, `📁 Archivo subido: ${file.name}`]);
    } catch (err) {
      console.error("Upload error:", err);
      setMessages((prev) => [...prev, { text: "Error al subir archivo.", sender: "system" }]);
      setHistory((prev) => [...prev, "⚠️ Error al subir archivo."]);
    }
  };

  // --------------------------
  //  Documents: list & delete
  // --------------------------
  const handleListDocuments = async () => {
    try {
      const resp = await fetch(`${API_BASE}/documents`);
      if (!resp.ok) {
        console.error("GET /documents failed:", resp.status);
        setMessages((prev) => [...prev, { text: "Error al obtener documentos.", sender: "system" }]);
        return;
      }
      const data = await resp.json();
      // backend returns { documentos: [...] }
      const docs = Array.isArray(data.documentos) ? data.documentos : [];
      setDocuments(docs);
      setShowSidebar(true);
      if (!docs.length) {
        setMessages((prev) => [...prev, { text: "No hay documentos disponibles.", sender: "system" }]);
      }
    } catch (err) {
      console.error("Error fetching documents:", err);
      setMessages((prev) => [...prev, { text: "Error al cargar documentos.", sender: "system" }]);
    }
  };

  const handleDeleteDocument = async (id) => {
    try {
      const resp = await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });
      if (!resp.ok) {
        console.error("DELETE failed:", resp.status);
        setMessages((prev) => [...prev, { text: "Error al eliminar documento.", sender: "system" }]);
        return;
      }
      // remove locally
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      setMessages((prev) => [...prev, { text: "Documento eliminado.", sender: "system" }]);
    } catch (err) {
      console.error("Error deleting document:", err);
      setMessages((prev) => [...prev, { text: "Error al eliminar documento.", sender: "system" }]);
    }
  };

  // Filtered documents by docSearch
  const filteredDocs = documents.filter((d) => d.nombre.toLowerCase().includes(docSearch.toLowerCase()));

  // Clear history
  const handleClearHistory = () => {
    setMessages([]);
    setHistory([]);
    localStorage.removeItem("chatHistory");
  };

  return (
    <MDBox pt={6} px={6} pb={6} sx={{ position: "relative" }}>
      {/* Volver */}
      <Button
        variant="contained"
        color="info"
        startIcon={<Icon>arrow_back</Icon>}
        onClick={() => navigate("/dashboard")}
        sx={{ mb: 2 }}
      >
        Volver al inicio
      </Button>

      <Grid container spacing={4} justifyContent="center">
        {/* HISTORIAL (izquierda) */}
        <Grid item xs={12} md={3}>
          <Card sx={{ p: 3, height: "85vh", overflowY: "auto" }}>
            <MDBox display="flex" justifyContent="space-between" mb={2}>
              <MDTypography variant="h6" color="info">Historial</MDTypography>
              <Button color="error" onClick={handleClearHistory}><Icon>delete</Icon></Button>
            </MDBox>

            <TextField
              fullWidth
              placeholder="Buscar en historial..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{ mb: 2 }}
            />

            <Divider sx={{ mb: 2 }} />

            {filteredHistory.map((item, i) => (
              <MDBox key={i} mb={1}>
                <MDTypography variant="body2">{item}</MDTypography>
              </MDBox>
            ))}

          </Card>
        </Grid>

        {/* CHAT (centro) */}
        <Grid item xs={12} md={9}>
          <Card sx={{ p: 4, height: "85vh", display: "flex", flexDirection: "column", position: "relative" }}>
            <MDTypography variant="h5" color="info" mb={2} textAlign="center">
              Chat Medistrust
            </MDTypography>

            <MDBox display="flex" justifyContent="center" mb={2}>
              <FormControl size="small" sx={{ minWidth: 280 }}>
                <InputLabel>Modelo IA</InputLabel>
                <Select
                  value={selectedModel}
                  label="Modelo IA"
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  {models.hf.length > 0 && (
                    <MenuItem disabled sx={{ fontWeight: "bold", opacity: 0.7 }}>
                      ─ HF API (online) ─
                    </MenuItem>
                  )}
                  {models.hf.map((m) => (
                    <MenuItem key={m.id} value={m.id}>
                      {m.name} — {m.size} ({m.description})
                    </MenuItem>
                  ))}
                  {models.ollama.length > 0 && (
                    <MenuItem disabled sx={{ fontWeight: "bold", opacity: 0.7, mt: 1 }}>
                      ─ Ollama (local) ─
                    </MenuItem>
                  )}
                  {models.ollama.map((m) => (
                    <MenuItem key={m.id} value={m.id}>
                      {m.name} — {m.size} ({m.description})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </MDBox>

            <MDBox sx={{ flex: 1, overflowY: "auto", mb: 2 }}>
              {loading && (
                <MDBox display="flex" justifyContent="center" mb={2}>
                  <Mirage size="60" speed="2.5" color="black" />
                </MDBox>
              )}

              {messages.map((msg, i) => (
                <MDBox
                  key={i}
                  display="flex"
                  justifyContent={msg.sender === "user" ? "flex-end" : "flex-start"}
                  mb={1}
                >
                  <MDBox
                    px={2}
                    py={1}
                    borderRadius="10px"
                    sx={{
                      backgroundColor: msg.sender === "user" ? "#1a73e8" : "#e0e0e0",
                      color: msg.sender === "user" ? "white" : "black",
                      maxWidth: "80%",
                      wordBreak: "break-word",
                    }}
                  >
                    <MDTypography>{msg.text}</MDTypography>
                  </MDBox>
                </MDBox>
              ))}
            </MDBox>

            <MDBox display="flex" gap={1} mb={1}>
              <TextField
                fullWidth
                placeholder="Escribe un mensaje..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !loading && !isSendingRef.current) {
                    e.preventDefault();
                    e.stopPropagation();
                    handleSend();
                  }
                }}
                disabled={loading}
              />
              <Button variant="contained" color="info" onClick={(e) => { e.preventDefault(); handleSend(); }} disabled={loading}><Icon>send</Icon></Button>
              <Button variant="contained" color="error" onClick={handleStopIA}><Icon>stop</Icon> Detener IA</Button>
            </MDBox>

            <MDBox display="flex" gap={1} justifyContent="center" mb={1}>
              <Button
                variant="contained"
                color="info"
                component="label"
                startIcon={<Icon>upload_file</Icon>}
              >
                Subir consultas (Excel)
                <input hidden type="file" accept=".xls,.xlsx" onChange={handleFileUpload} />
              </Button>

              <Button
                variant="contained"
                color="info"
                startIcon={<Icon>folder</Icon>}
                onClick={handleListDocuments}
              >
                Listar documentos
              </Button>
            </MDBox>

            <MDTypography variant="caption" color="text" textAlign="center">
              {currentTaskId ? `Task: ${currentTaskId}` : ""}
            </MDTypography>
          </Card>
        </Grid>
      </Grid>

      {/* ---------------------------
          Sidebar lateral derecho (overlay) - animado
         --------------------------- */}
      <MDBox
        sx={{
          position: "fixed",
          top: "80px",
          right: 24,
          width: 360,
          height: "75vh",
          zIndex: 1400,
          boxShadow: 3,
          borderRadius: 2,
          background: "white",
          transform: showSidebar ? "translateX(0)" : "translateX(110%)",
          transition: "transform 300ms ease-in-out",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <MDBox display="flex" alignItems="center" justifyContent="space-between" p={2} borderBottom="1px solid #eee">
          <MDTypography variant="h6" color="info">Documentos</MDTypography>
          <MDBox>
            <Button size="small" onClick={() => setShowSidebar(false)}><Icon>close</Icon></Button>
          </MDBox>
        </MDBox>

        {/* Search dentro del panel */}
        <MDBox p={2} borderBottom="1px solid #f0f0f0">
          <TextField
            fullWidth
            placeholder="Buscar documentos..."
            value={docSearch}
            onChange={(e) => setDocSearch(e.target.value)}
          />
        </MDBox>

        {/* Lista */}
        <MDBox sx={{ height: "calc(100% - 120px)", overflowY: "auto", p: 2 }}>
          {Array.isArray(filteredDocs) && filteredDocs.length > 0 ? (
            filteredDocs.map((doc) => (
              <MDBox key={doc.id} display="flex" justifyContent="space-between" alignItems="center" mb={1} p={1} sx={{ borderRadius: 1, background: "#fafafa" }}>
                <MDBox>
                  <MDTypography variant="body2" sx={{ fontWeight: 500 }}>{doc.nombre}</MDTypography>
                  <MDTypography variant="caption" color="text">Ruta: {doc.ruta}</MDTypography>
                </MDBox>

                <MDBox display="flex" gap={1}>
                  <Button size="small" color="info" onClick={() => {
                    // opción: podrías abrir/descargar el archivo aquí usando doc.ruta
                    window.open(`file://${doc.ruta}`);
                  }}>
                    <Icon>launch</Icon>
                  </Button>

                  <Button size="small" color="error" onClick={() => handleDeleteDocument(doc.id)}>
                    <Icon>delete</Icon>
                  </Button>
                </MDBox>
              </MDBox>
            ))
          ) : (
            <MDBox textAlign="center" mt={4}>
              <MDTypography variant="body2" color="text">No hay documentos disponibles.</MDTypography>
            </MDBox>
          )}
        </MDBox>

        {/* Footer */}
        <MDBox p={2} borderTop="1px solid #eee" display="flex" justifyContent="space-between">
          <Button variant="outlined" size="small" onClick={() => {
            setShowSidebar(false);
          }}>
            Cerrar
          </Button>
          <Button variant="contained" size="small" color="info" onClick={handleListDocuments}>
            Refrescar
          </Button>
        </MDBox>
      </MDBox>
    </MDBox>
  );
}

export default Medistrust;
