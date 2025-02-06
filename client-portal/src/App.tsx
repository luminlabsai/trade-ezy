import { ThemeProvider, CssBaseline, createTheme } from "@mui/material";
import { AuthProvider, useAuth } from "./context/AuthContext"; // Import useAuth
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Services from "./pages/Services";
import ChatHistory from "./pages/ChatHistory";
import Account from "./pages/Account";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import { Navigate } from "react-router-dom";

const theme = createTheme(); // MUI theme

function AppContent() {
  const { currentUser } = useAuth(); // ✅ Use correct property name
  return (
    <>
      <Navbar />
      <div style={{ display: "flex" }}>
        <Sidebar />
        <div style={{ flex: 1, padding: "20px" }}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/dashboard" element={<Navigate to="/account" replace />} /> {/* ✅ Redirects to Account */}
            <Route path="/services" element={<ProtectedRoute><Services /></ProtectedRoute>} />
            <Route path="/chathistory" element={<ProtectedRoute><ChatHistory /></ProtectedRoute>} />
            <Route path="/account" element={<ProtectedRoute><Account /></ProtectedRoute>} /> {/* ✅ Correct Account route */}
            <Route path="*" element={<Navigate to="/account" replace />} /> {/* ✅ Redirects all unknown paths to Account */}
          </Routes>
        </div>
      </div>
    </>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </Router>
    </ThemeProvider>
  );
}

export default App;
