const AI_API_BASE = import.meta.env.VITE_AI_API_URL || "http://127.0.0.1:8000";

export const fetchDashboardData = async () => {
  try {
    const response = await fetch(`${AI_API_BASE}/dashboard`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` },
    });
    return await response.json();
  } catch (error) {
    console.error("Error fetching dashboard data:", error);
    return null;
  }
};