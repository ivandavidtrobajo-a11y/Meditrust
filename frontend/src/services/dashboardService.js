const AI_API_BASE = import.meta.env.VITE_AI_API_URL || "";

export const fetchDashboardData = async () => {
  try {
    const response = await fetch(`${AI_API_BASE}/dashboard`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching dashboard data:", error);
    return null;
  }
};
