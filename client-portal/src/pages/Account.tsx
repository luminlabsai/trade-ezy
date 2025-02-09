import React, { useEffect, useState } from "react";
import { getAccountDetails, updateAccountDetails } from "../api/account";
import AccountTable from "@components/AccountTable"; // ✅ Import the reusable component
import { useAuth } from "../context/AuthContext"; // ✅ Access dynamic businessId

const AccountPage: React.FC = () => {
  const { businessId } = useAuth(); // ✅ Dynamically fetch businessId from context
  const [accountData, setAccountData] = useState<any>(null); // State for account details
  const [loading, setLoading] = useState(true); // State to track loading status

  // Fetch account details when businessId changes
  useEffect(() => {
    if (!businessId) return; // Skip if businessId is not available

    const fetchAccount = async () => {
      try {
        const data = await getAccountDetails(businessId); // Fetch details from API
        setAccountData(data); // Update account data state
      } catch (error) {
        // Suppressed logging for production
        // console.error("❌ Failed to load account data:", error);
      } finally {
        setLoading(false); // Ensure loading stops even on error
      }
    };

    fetchAccount();
  }, [businessId]); // Re-run if businessId changes

  // Function to handle saving updates
  const handleSave = async (updatedData: any) => {
    if (!businessId) {
      // console.error("❌ Error: Business ID is missing");
      return; // Prevent saving without businessId
    }

    try {
      await updateAccountDetails(businessId, updatedData); // Call API to save updates
      setAccountData((prevData: any) => ({ ...prevData, ...updatedData })); // Merge changes
    } catch (error) {
      // Suppressed logging for production
      // console.error("❌ Failed to update account data:", error);
    }
  };

  // Render loading state
  if (!businessId || loading) {
    return <p className="text-gray-600 text-center mt-6">⏳ Loading...</p>;
  }

  // Render account data or fallback message
  return (
    <div className="max-w-3xl mx-auto p-6">
      {accountData ? (
        <AccountTable {...accountData} onSave={handleSave} />
      ) : (
        <p className="text-gray-600 text-center">
          No account data available. Please check your business details.
        </p>
      )}
    </div>
  );
};

export default AccountPage;
