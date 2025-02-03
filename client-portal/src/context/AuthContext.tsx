import React, { createContext, useContext, useEffect, useState } from "react";
import { auth } from "../firebase";
import { api } from "../api";

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
          const idToken = await user.getIdToken(true);
          console.log("🔥 Firebase ID Token:", idToken);


          const response = await api.get("/api/getBusinessId", {
            headers: {
              Authorization: `Bearer ${idToken}`,
              "Content-Type": "application/json",
            },
          });

          console.log("✅ Business ID Response:", response.data);
          setBusinessId(response.data.business_id);
        } catch (error) {
          console.error("🚨 Error fetching business ID:", error.response?.data || error.message);
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
