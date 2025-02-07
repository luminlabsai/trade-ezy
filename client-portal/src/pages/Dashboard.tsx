import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { getServices } from "../api";



interface Service {
  service_id: string;
  service_name: string;
  description: string;
  duration_minutes: number;
  price: number;
}

const Dashboard: React.FC = () => {
  const { businessId } = useAuth();
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchServices = async () => {
      if (businessId) {
        try {
          const data = await getServices(businessId);
          setServices(data);
        } catch (err) {
          console.error("Error fetching services:", err);
          setError("Failed to load services.");
        } finally {
          setLoading(false);
        }
      }
    };

    fetchServices();
  }, [businessId]);

  return (
    <div style={{ padding: "20px" }}>
      <h1>Dashboard</h1>
      <h2>Services</h2>

      {loading && <p>Loading services...</p>}
      {error && <p className="text-red-500">{error}</p>}

      {services.length > 0 ? (
        <table className="border-collapse border border-gray-300 w-full mt-4">
          <thead>
            <tr className="bg-gray-200">
              <th className="border border-gray-300 px-4 py-2">Service Name</th>
              <th className="border border-gray-300 px-4 py-2">Description</th>
              <th className="border border-gray-300 px-4 py-2">Duration (mins)</th>
              <th className="border border-gray-300 px-4 py-2">Price ($)</th>
            </tr>
          </thead>
          <tbody>
            {services.map((service) => (
              <tr key={service.service_id} className="hover:bg-gray-100">
                <td className="border border-gray-300 px-4 py-2">{service.service_name}</td>
                <td className="border border-gray-300 px-4 py-2">{service.description}</td>
                <td className="border border-gray-300 px-4 py-2 text-center">{service.duration_minutes}</td>
                <td className="border border-gray-300 px-4 py-2 text-center">${service.price.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No services found.</p>
      )}
    </div>
  );
};

export default Dashboard;
