import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { fetchServices, deleteSelectedServices } from "../api/services";

interface Service {
  service_id: string;
  service_name: string;
  description: string;
  duration_minutes: number;
  price: number;
}

const Services: React.FC = () => {
  const { businessId } = useAuth();
  const [services, setServices] = useState<Service[]>([]);
  const [selectedServices, setSelectedServices] = useState<string[]>([]);

  useEffect(() => {
    if (businessId) {
      fetchServices(businessId)
        .then((data: Service[]) => setServices(data))
        .catch((error: unknown) => {
          console.error("Error fetching services:", error);
        });
    }
  }, [businessId]);

  // Handle checkbox selection
  const toggleSelection = (serviceId: string) => {
    setSelectedServices((prev) =>
      prev.includes(serviceId)
        ? prev.filter((id) => id !== serviceId) // Deselect if already selected
        : [...prev, serviceId] // Select otherwise
    );
  };

  // Handle delete button click
  const handleDelete = async () => {
    if (selectedServices.length > 0) {
      const confirmation = window.prompt(
        `Type "delete" to confirm deleting ${selectedServices.length} services:`
      );

      if (confirmation === "delete") {
        await deleteSelectedServices(selectedServices);
        setServices((prev) => prev.filter((s) => !selectedServices.includes(s.service_id)));
        setSelectedServices([]); // Clear selection after deletion
      }
    }
  };

  return (
    <div style={{ padding: "20px" }}>
      <h2>Services</h2>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          border: "1px solid #ddd",
          marginTop: "10px",
        }}
      >
        <thead>
          <tr style={{ backgroundColor: "#f4f4f4" }}>
            <th style={{ border: "1px solid #ddd", padding: "10px" }}>Select</th>
            <th style={{ border: "1px solid #ddd", padding: "10px" }}>Service Name</th>
            <th style={{ border: "1px solid #ddd", padding: "10px" }}>Price</th>
            <th style={{ border: "1px solid #ddd", padding: "10px" }}>Duration</th>
          </tr>
        </thead>
        <tbody>
          {services.map((service) => (
            <tr key={service.service_id}>
              <td style={{ border: "1px solid #ddd", padding: "10px", textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={selectedServices.includes(service.service_id)}
                  onChange={() => toggleSelection(service.service_id)}
                />
              </td>
              <td style={{ border: "1px solid #ddd", padding: "10px" }}>{service.service_name}</td>
              <td style={{ border: "1px solid #ddd", padding: "10px" }}>${service.price}</td>
              <td style={{ border: "1px solid #ddd", padding: "10px" }}>
                {service.duration_minutes} min
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Delete Button */}
      <button
        onClick={handleDelete}
        disabled={selectedServices.length === 0}
        style={{
          marginTop: "20px",
          padding: "10px 20px",
          fontSize: "16px",
          cursor: selectedServices.length > 0 ? "pointer" : "not-allowed",
          backgroundColor: selectedServices.length > 0 ? "#c0392b" : "#ccc",
          color: "#fff",
          border: "none",
          borderRadius: "5px",
        }}
      >
        Delete Selected Services
      </button>
    </div>
  );
};

export default Services;
