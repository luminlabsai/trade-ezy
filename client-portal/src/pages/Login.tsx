import React from "react";
import { signInWithPopup } from "firebase/auth";
import { auth, googleProvider } from "../firebase";
import { useNavigate } from "react-router-dom";

const Login: React.FC = () => {
  const navigate = useNavigate();

  const handleGoogleLogin = async () => {
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const user = result.user;
      console.log("Logged in user:", user);
      navigate("/dashboard"); // Redirect to the dashboard after login
    } catch (error) {
      console.error("Error during login:", error);
    }
  };

  return (
    <div style={{ textAlign: "center", marginTop: "50px" }}>
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
        }}
      >
        Sign in with Google
      </button>
    </div>
  );
};

export default Login;