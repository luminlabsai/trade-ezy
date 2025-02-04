const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const fetchServices = async (businessId: string) => {
  try {
    const response = await fetch(`${BASE_URL}/api/manageBusinessServices`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ businessID: businessId }),
    });

    if (!response.ok) {
      throw new Error("Failed to fetch services");
    }

    const data = await response.json();
    return data.services || [];
  } catch (error) {
    console.error("Error fetching services:", error);
    return [];
  }
};

export const deleteSelectedServices = async (serviceIDs: string[]) => {
  try {
    const response = await fetch(`${BASE_URL}/api/manageBusinessServices`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ serviceIDs }),
    });

    if (!response.ok) {
      throw new Error("Failed to delete services");
    }

    return await response.json();
  } catch (error) {
    console.error("Error deleting services:", error);
  }
};
