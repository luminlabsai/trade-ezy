import React, { useEffect, useState } from "react";
import { fetchServices, deleteSelectedServices } from "../api/services";
import { useAuth } from "../context/AuthContext";

interface Service {
  service_id: string;
  service_name: string;
  description: string;
  duration_minutes: number;
  price: number;
}

const ServicesTable: React.FC = () => {
  const { businessId } = useAuth();
  const [services, setServices] = useState<Service[]>([]);
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (businessId) {
      fetchServices(businessId)
        .then((data) => {
          setServices(data);
          setLoading(false);
        })
        .catch((err) => {
          console.error("❌ Failed to fetch services:", err);
          setError("Failed to load services.");
          setLoading(false);
        });
    }
  }, [businessId]);

  // Handle checkbox selection
  const toggleSelection = (serviceId: string) => {
    setSelectedServices((prev) =>
      prev.includes(serviceId)
        ? prev.filter((id) => id !== serviceId) // Deselect
        : [...prev, serviceId] // Select
    );
  };

  // Handle delete
  const handleDelete = async () => {
    if (selectedServices.length > 0) {
      const confirmation = window.prompt(
        `Type "delete" to confirm removing ${selectedServices.length} services:`
      );

      if (confirmation === "delete") {
        await deleteSelectedServices(selectedServices);
        setServices((prev) => prev.filter((s) => !selectedServices.includes(s.service_id)));
        setSelectedServices([]); // Clear selection
      }
    }
  };

  if (loading) return <p>Loading services...</p>;
  if (error) return <p className="text-red-500">{error}</p>;

  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold mb-4">Services</h2>
      <table className="min-w-full bg-white border border-gray-200">
        <thead>
          <tr className="bg-gray-100">
            <th className="border px-4 py-2">
              <input
                type="checkbox"
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedServices(services.map((s) => s.service_id)); // Select all
                  } else {
                    setSelectedServices([]); // Deselect all
                  }
                }}
                checked={selectedServices.length === services.length && services.length > 0}
              />
            </th>
            <th className="border px-4 py-2">Service Name</th>
            <th className="border px-4 py-2">Description</th>
            <th className="border px-4 py-2">Duration (mins)</th>
            <th className="border px-4 py-2">Price ($)</th>
          </tr>
        </thead>
        <tbody>
          {services.length > 0 ? (
            services.map((service) => (
              <tr key={service.service_id} className="hover:bg-gray-50">
                <td className="border px-4 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={selectedServices.includes(service.service_id)}
                    onChange={() => toggleSelection(service.service_id)}
                  />
                </td>
                <td className="border px-4 py-2">{service.service_name}</td>
                <td className="border px-4 py-2">{service.description}</td>
                <td className="border px-4 py-2 text-center">{service.duration_minutes}</td>
                <td className="border px-4 py-2 text-center">${service.price.toFixed(2)}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={5} className="border px-4 py-2 text-center">
                No services found.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Delete Button */}
      <button
        onClick={handleDelete}
        disabled={selectedServices.length === 0}
        className={`mt-4 px-4 py-2 rounded text-white ${
          selectedServices.length > 0 ? "bg-red-600 hover:bg-red-700" : "bg-gray-400 cursor-not-allowed"
        }`}
      >
        Delete Selected Services
      </button>
    </div>
  );
};

export default ServicesTable;
