import React, { createContext, useContext, useEffect, useState } from "react";
import { auth } from "../firebase";

interface AuthContextType {
  currentUser: any;
  businessId: string | null;
  getIdToken: () => Promise<string | null>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [businessId, setBusinessId] = useState<string | null>(null);

  const getIdToken = async () => {
    if (currentUser) {
      try {
        return await currentUser.getIdToken();
      } catch (error) {
        console.error("❌ Error fetching Firebase ID token:", error);
      }
    }
    return null;
  };

  useEffect(() => {
    const unsubscribe = auth.onAuthStateChanged(async (user) => {
      setCurrentUser(user);

      if (user) {
        try {
          const idToken = await user.getIdToken();
          console.log("🔥 Firebase ID Token:", idToken);

          const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/getBusinessId`, {
            headers: {
              Authorization: `Bearer ${idToken}`,
              "Content-Type": "application/json",
            },
          });

          if (!response.ok) throw new Error("Failed to fetch Business ID");

          const data = await response.json();
          console.log("✅ Business ID Response:", data);
          setBusinessId(data.business_id);
        } catch (error) {
          console.error("🚨 Error fetching business ID:", error);
          setBusinessId(null);
        }
      } else {
        setBusinessId(null);
      }
    });

    return unsubscribe;
  }, []);

  return (
    <AuthContext.Provider value={{ currentUser, businessId, getIdToken }}>
      {children}
    </AuthContext.Provider>
  );
};

// ✅ Custom hook
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
