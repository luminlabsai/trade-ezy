import axios from "axios";

// ✅ Two base URLs for different function apps
const API_AUTH_BASE_URL = import.meta.env.VITE_API_BASE_URL; // 7071 for authentication
const API_SERVICES_BASE_URL = import.meta.env.VITE_API_BASE_URL2; // 7075 for business services

// ✅ Axios instances for both function apps
export const authApi = axios.create({
  baseURL: API_AUTH_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export const servicesApi = axios.create({
  baseURL: API_SERVICES_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// ✅ Re-export for compatibility
export const api = authApi; 

// ✅ Function to get services for a business
export const getServices = async (businessId: string) => {
  try {
    const response = await servicesApi.get(`/api/manageBusinessServices`, {
      params: { business_id: businessId },
    });
    return response.data;
  } catch (error) {
    console.error("🚨 Error fetching services:", error);
    throw error;
  }
};
