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
            to="/dashboard"
            style={{ color: "#647a5c", textDecoration: "none" }}
          >
            Dashboard
          </Link>
        </li>
        <li>
          <Link
            to="/services"
            style={{ color: "#647a5c", textDecoration: "none" }}
          >
            Services
          </Link>
        </li>
        <li>
          <Link
            to="/chat-history"
            style={{ color: "#647a5c", textDecoration: "none" }}
          >
            Chat History
          </Link>
        </li>
        <li>
          <Link
            to="/users"
            style={{ color: "#647a5c", textDecoration: "none" }}
          >
            Users
          </Link>
        </li>
      </ul>
    </div>
  );
};

export default Sidebar;