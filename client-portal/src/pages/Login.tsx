import React from "react";
import { signInWithPopup } from "firebase/auth";
import { auth, googleProvider } from "../firebase";
import { useNavigate } from "react-router-dom";

const Login: React.FC = () => {
  const navigate = useNavigate();

  const handleGoogleLogin = async () => {
    try {
      await signInWithPopup(auth, googleProvider);

      if (import.meta.env.MODE === "development") {
        console.log("🔍 Debug: User logged in successfully");
      }

      navigate("/dashboard"); // Redirect to dashboard after successful login
    } catch (error) {
      console.error("Error during login:", error);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh", // Full screen height
        flexDirection: "column",
      }}
    >
      <h1>Login</h1>
      <button
        onClick={handleGoogleLogin}
        style={{
          padding: "10px 20px",
          fontSize: "16px",
          cursor: "pointer",
          backgroundColor: "#647a5c",
          color: "#fff",
          border: "none",
          borderRadius: "5px",
          marginTop: "20px",
        }}
      >
        Sign in with Google
      </button>
    </div>
  );
};

export default Login;
