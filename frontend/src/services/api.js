import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", error.response || error.message);
    return Promise.reject(error);
  },
);

// Save interaction from structured form
export const logInteraction = (interactionData) => {
  return api.post("/interactions/", interactionData);
};

// AI Chat
export const sendChat = (message) => {
  return api.post("/chat", { message });
};

// Get interaction details
export const getInteraction = (interactionId) => {
  return api.get(`/interactions/${interactionId}`);
};

// Update interaction
export const updateInteraction = (interactionId, data) => {
  return api.put(`/interactions/${interactionId}`, data);
};

// Search HCP
export const searchHCP = (query, signal) => {
  return api.get("/hcps/search", {
    params: { q: query },
    signal,
  });
};
export const updateHCP = (id, data) => {
  return api.put(`/hcps/${id}`, data);
};
// Get all HCPs
export const getHCPs = () => {
  return api.get("/hcps/");
};

// Create HCP
export const createHCP = (hcpData) => {
  return api.post("/hcps/", hcpData);
};

// Get interaction history
export const getInteractionHistory = (hcpId) => {
  return api.get(`/interactions/history/${hcpId}`);
};

// Health check
export const healthCheck = () => {
  return api.get("/health");
};

export default api;
