import React from "react";
import { useAuth } from "../context/AuthContext";
import { signOut } from "firebase/auth";
import { auth } from "../firebase";
import { useNavigate } from "react-router-dom";

const Navbar: React.FC = () => {
  const { currentUser } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await signOut(auth);
      navigate("/login");
    } catch (error) {
      console.error("Error during logout:", error);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 20px",
        backgroundColor: "#898B91",
        color: "#fff",
        height: "60px",
      }}
    >
      {/* Left Side (Spacer for alignment) */}
      <div style={{ width: "100px" }}></div>

      {/* Centered Logo */}
      <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
        <img
          src="/media/logo.png"
          alt="Trade-Ezy Logo"
          style={{
            height: "40px",
            maxWidth: "200px",
            objectFit: "contain",
          }}
        />
      </div>

      {/* Right Side (Logout Button) */}
      {currentUser && (
        <button
          onClick={handleLogout}
          style={{
            padding: "8px 15px",
            backgroundColor: "#FDBE42", // ✅ Updated logout button color
            color: "#333",
            fontWeight: "bold",
            border: "none",
            borderRadius: "5px",
            cursor: "pointer",
            transition: "background 0.3s",
          }}
        >
          Logout
        </button>
      )}
    </div>
  );
};

export default Navbar;
