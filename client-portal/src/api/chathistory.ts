import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "https://trade-ezy-businessfunctions.azurewebsites.net/api";


export const fetchChatHistory = async (
    businessId: string, 
    fromDate?: string, 
    toDate?: string, 
    limit: number = 20, 
    offset: number = 0
) => {
    try {
        const params = new URLSearchParams({
            business_id: businessId,
            limit: limit.toString(),
            offset: offset.toString(),
        });

        if (fromDate) params.append("from_date", fromDate);
        if (toDate) params.append("to_date", toDate);

        const response = await axios.get(`${API_BASE_URL}/api/getChatHistory`, { params });
        return response.data;
    } catch (error) {
        console.error("Error fetching chat history:", error);
        throw error;
    }
};
