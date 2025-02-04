import React from "react";
import { Link } from "react-router-dom";

const Sidebar: React.FC = () => {
  return (
    <div
      style={{
        width: "200px",
        height: "100vh",
        backgroundColor: "#444f61",
        padding: "20px",
      }}
    >
      <h2 style={{ color: "#fff" }}>Trade-Ezy</h2>
      <ul style={{ listStyle: "none", padding: 0 }}>
        <li>
          <Link
            to="/services"
            style={{ color: "#fff", textDecoration: "none", display: "block", padding: "10px 0" }}
          >
            Services
          </Link>
        </li>
        <li>
          <Link
            to="/chat-history"
            style={{ color: "#fff", textDecoration: "none", display: "block", padding: "10px 0" }}
          >
            Chat History
          </Link>
        </li>
        <li>
          <Link
            to="/users"
            style={{ color: "#fff", textDecoration: "none", display: "block", padding: "10px 0" }}
          >
            Account
          </Link>
        </li>
      </ul>
    </div>
  );
};

export default Sidebar;
