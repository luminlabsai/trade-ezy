// src/pages/Account.tsx

import React, { useEffect, useState } from "react";
import { getAccountDetails, updateAccountDetails } from "../api/account";
import AccountTable from "@components/AccountTable"; // ✅ Ensure correct import
import { useAuth } from "../context/AuthContext"; // ✅ Get businessId dynamically

const AccountPage: React.FC = () => {
  const { businessId } = useAuth(); // ✅ Get businessId from context
  const [accountData, setAccountData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!businessId) return; // ⛔️ Avoid fetching if businessId is not available

    const fetchAccount = async () => {
      try {
        const data = await getAccountDetails(businessId);
        setAccountData(data);
      } catch (error) {
        console.error("❌ Failed to load account data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchAccount();
  }, [businessId]); // ✅ Re-run when businessId changes

  const handleSave = async (updatedData: any) => {
    if (!businessId) {
      console.error("❌ Error: Business ID is missing");
      return;
    }

    try {
      await updateAccountDetails(businessId, updatedData);
      setAccountData((prevData: any) => ({ ...prevData, ...updatedData }));
    } catch (error) {
      console.error("❌ Failed to update account data:", error);
    }
  };

  if (!businessId) return <p className="text-red-500 text-center mt-6">⚠️ Error: Business ID is missing</p>;
  if (loading) return <p className="text-gray-600 text-center mt-6">⏳ Loading...</p>;

  return (
    <div className="max-w-3xl mx-auto p-6">
      {accountData ? (
        <AccountTable {...accountData} onSave={handleSave} />
      ) : (
        <p className="text-gray-600 text-center">No account data available.</p>
      )}
    </div>
  );
};

export default AccountPage;
