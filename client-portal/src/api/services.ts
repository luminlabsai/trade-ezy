const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const fetchServices = async (businessId: string) => {
    if (!businessId) {
      console.error("🚨 Error: businessId is missing or undefined.");
      return [];
    }
  
    console.log("📡 Fetching services for businessID:", businessId); // ✅ Debugging log
  
    try {
      const response = await fetch(`${BASE_URL}/api/manageBusinessServices?business_id=${businessId}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });
  
      console.log("📡 Response status:", response.status); // ✅ Log response status
  
      if (!response.ok) {
        const errorText = await response.text(); // Get response error message
        throw new Error(`Failed to fetch services: ${errorText}`);
      }
  
      const data = await response.json();
      console.log("✅ Fetched services:", data); // ✅ Debugging log
  
      return data || [];
    } catch (error) {
      console.error("🚨 Error fetching services:", error);
      return [];
    }
  };
  

export const deleteSelectedServices = async (serviceIDs: string[]) => {
  if (!serviceIDs || serviceIDs.length === 0) {
    console.error("🚨 Error: No service IDs provided for deletion.");
    return;
  }

  console.log("🗑️ Deleting services with IDs:", serviceIDs); // ✅ Debugging log

  try {
    const response = await fetch(`${BASE_URL}/api/manageBusinessServices`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ serviceIDs }),
    });

    console.log("🗑️ Response status:", response.status); // ✅ Log response status

    if (!response.ok) {
      const errorText = await response.text(); // Get response error message
      throw new Error(`Failed to delete services: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("🚨 Error deleting services:", error);
  }
};
