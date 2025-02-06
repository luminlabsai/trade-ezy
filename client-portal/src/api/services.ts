interface Service {
    service_id: string;
    service_name: string;
    description: string;
    duration_minutes: number;
    price: number;
  }
  
const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const fetchServices = async (businessId: string) => {
    if (!businessId) {
      console.error("🚨 Error: businessId is missing or undefined.");
      return [];
    }
  
    console.log("📡 Fetching services for businessID:", businessId);
  
    try {
      const response = await fetch(`${BASE_URL}/api/manageBusinessServices?business_id=${businessId}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });
  
      console.log("📡 Response status:", response.status);
  
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to fetch services: ${errorText}`);
      }
  
      const data = await response.json();
      console.log("✅ Fetched services:", data);
  
      return data || [];
    } catch (error) {
      console.error("🚨 Error fetching services:", error);
      return [];
    }
  };
  
export const deleteService = async (serviceId: string) => {
  if (!serviceId) {
    console.error("🚨 Error: No service ID provided for deletion.");
    return;
  }

  console.log("🗑️ Deleting service with ID:", serviceId);

  try {
    const response = await fetch(`${BASE_URL}/api/manageBusinessServices/${serviceId}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    });

    console.log("🗑️ Response status:", response.status);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to delete service: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("🚨 Error deleting service:", error);
  }
};

export const updateService = async (serviceId: string, updatedFields: any) => {
  if (!serviceId || !updatedFields) {
    console.error("🚨 Error: serviceId and updatedFields are required for updating.");
    return;
  }

  console.log("✏️ Updating service with ID:", serviceId, "Fields:", updatedFields);

  try {
    const response = await fetch(`${BASE_URL}/api/manageBusinessServices`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ service_id: serviceId, ...updatedFields }),
    });

    console.log("✏️ Response status:", response.status);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to update service: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("🚨 Error updating service:", error);
  }
};

export const addService = async (businessId: string, service: Omit<Service, "service_id">) => {
    const BASE_URL = import.meta.env.VITE_API_BASE_URL;
  
    try {
      const response = await fetch(`${BASE_URL}/api/manageBusinessServices`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          business_id: businessId,
          ...service,
        }),
      });
  
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to add service: ${errorText}`);
      }
  
      return await response.json(); // Return the new service from backend
    } catch (error) {
      console.error("🚨 Error adding service:", error);
      throw error;
    }
  };
  