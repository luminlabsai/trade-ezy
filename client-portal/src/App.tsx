import { ThemeProvider, CssBaseline, createTheme, Button } from "@mui/material";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Services from "./pages/Services";
import ChatHistory from "./pages/ChatHistory";
import Account from "./pages/Account";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import { signInWithPopup, GoogleAuthProvider } from "firebase/auth";
import { auth } from "./firebase";

// ✅ Define MUI theme with custom button styles
const theme = createTheme({
  palette: {
    primary: { main: "#FDBE42", dark: "#E6A935" },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          backgroundColor: "#FDBE42",
          color: "#333",
          fontWeight: "bold",
          "&:hover": { backgroundColor: "#E6A935" },
        },
      },
    },
  },
});

function AppContent() {
  const { currentUser } = useAuth();
  const location = useLocation();
  const isLoginScreen = location.pathname === "/login";

  // ✅ Google Sign-In Function
  const handleGoogleSignIn = async () => {
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
      console.log("✅ Google login successful");
    } catch (error) {
      console.error("🚨 Google Sign-In Failed:", error);
    }
  };

  // ✅ Redirect logged-in users away from login screen
  if (currentUser && isLoginScreen) return <Navigate to="/account" replace />;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        width: "100vw",
        backgroundColor: "#898B91",
        overflow: "hidden",
      }}
    >
      {!isLoginScreen && <Navbar />}
      <div style={{ display: "flex", flex: 1 }}>
        {!isLoginScreen && currentUser && <Sidebar />}
        {isLoginScreen ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            <img src="/media/logo.png" alt="Trade-Ezy Logo" style={{ width: "300px" }} />
            <Button variant="contained" sx={{ mt: 3 }} onClick={handleGoogleSignIn}>
              Sign in with Google
            </Button>
          </div>
        ) : (
          <div
            style={{
              flex: 1,
              backgroundColor: "white",
              padding: "20px",
              borderRight: "20px solid #898B91",
              borderBottom: "20px solid #898B91",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: "calc(100vh - 60px)",
              width: "calc(100vw - 220px)",
            }}
          >
            <Routes>
              <Route path="/login" element={<Navigate to="/account" replace />} />
              <Route path="/services" element={<ProtectedRoute><Services /></ProtectedRoute>} />
              <Route path="/chathistory" element={<ProtectedRoute><ChatHistory /></ProtectedRoute>} />
              <Route path="/account" element={<ProtectedRoute><Account /></ProtectedRoute>} />
              <Route path="*" element={<Navigate to="/account" replace />} />
            </Routes>
          </div>
        )}
      </div>
    </div>
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
