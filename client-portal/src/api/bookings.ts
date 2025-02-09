import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const fetchBookings = async (
  businessId: string,
  rowsPerPage: number, // Moved to appear before optional parameters
  offset: number,      // Moved to appear before optional parameters
  fromDate?: string,   // Optional parameters now follow
  toDate?: string,
  serviceName?: string
): Promise<any> => {
  try {
    // Define params with dynamic keys
    const params: Record<string, string | number> = {
      business_id: businessId,
      offset,
      limit: rowsPerPage,
    };

    // Add optional params if provided
    if (fromDate) params.from_date = fromDate;
    if (toDate) params.to_date = toDate;
    if (serviceName) params.service_name = serviceName;

    const response = await axios.get(`${BASE_URL}/api/getBookings`, { params });
    return response.data;
  } catch (error) {
    console.error("Failed to fetch bookings:", error);
    throw error;
  }
};
