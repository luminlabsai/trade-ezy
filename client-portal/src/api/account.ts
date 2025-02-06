// src/api/account.ts

import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "https://trade-ezy-businessfunctions.azurewebsites.net/api";

export const getAccountDetails = async (businessId: string) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/manageAccounts`, {
      params: { business_id: businessId },
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching account details:", error);
    throw error;
  }
};

export const updateAccountDetails = async (businessId: string, updatedData: any) => {
    console.log("📡 Sending update request:", businessId, updatedData);
  
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/manageAccounts?business_id=${businessId}`,  // ✅ Ensure business_id is in the URL
        updatedData, 
        {
          headers: { "Content-Type": "application/json" },  // ✅ Ensure proper headers
        }
      );
  
      console.log("✅ Response from backend:", response.data);
      return response.data;
    } catch (error) {
      console.error("❌ Error updating account:", error);
      throw error;
    }
  };
