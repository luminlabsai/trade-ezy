import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext"; // ✅ Now this works
import { getServices } from "../api";

const Dashboard: React.FC = () => {
  const { currentUser, businessId } = useAuth(); // ✅ Use businessId here
  const [services, setServices] = useState<any[]>([]);

  useEffect(() => {
    const fetchServices = async () => {
      if (currentUser && businessId) { // ✅ Now using businessId from context
        try {
          const data = await getServices(businessId);
          setServices(data);
        } catch (error) {
          console.error("Error fetching services:", error);
        }
      }
    };

    fetchServices();
  }, [currentUser, businessId]);

  return (
    <div style={{ padding: "20px" }}>
      <h1>Dashboard</h1>
      <h2>Services</h2>
      {services.length > 0 ? (
        <ul>
          {services.map((service) => (
            <li key={service.id}>{service.name}</li>
          ))}
        </ul>
      ) : (
        <p>No services found.</p>
      )}
    </div>
  );
};

export default Dashboard;
