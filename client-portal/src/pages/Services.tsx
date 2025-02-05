import React from "react";
import ServicesTable from "../components/ServicesTable";

const Services: React.FC = () => {
  return (
    <div style={{ padding: "20px" }}>
      <h2>Services</h2>
      <ServicesTable />
    </div>
  );
};

export default Services;
