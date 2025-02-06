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

      <ul style={{ listStyle: "none", padding: 0 }}>

      <li>
          <Link
            to="/users"
            style={{ color: "#fff", textDecoration: "none", display: "block", padding: "10px 0" }}
          >
            Account
          </Link>
        </li>




        <li>
          <Link
            to="/chathistory"
            style={{ color: "#fff", textDecoration: "none", display: "block", padding: "10px 0" }}
          >
            Chat History
          </Link>
        </li>



        <li>
          <Link
            to="/services"
            style={{ color: "#fff", textDecoration: "none", display: "block", padding: "10px 0" }}
          >
            Services
          </Link>
        </li>

      </ul>
    </div>
  );
};

export default Sidebar;
