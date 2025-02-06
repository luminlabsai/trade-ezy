import React from "react";
import ChatHistoryTable from "../components/ChatHistoryTable";
import { useAuth } from "../context/AuthContext"; // ✅ Ensure correct import

console.log("✅ ChatHistory.tsx is rendering");

const ChatHistory: React.FC = () => {
  const { businessId } = useAuth(); // ✅ Get businessId from context

  console.log("🛠️ Business ID:", businessId); // ✅ Debugging log

  if (!businessId) {
    return <div>Loading business data...</div>; // Prevents API call with undefined ID
  }

  return (
    <div>
      <h1>Chat History</h1>
      <ChatHistoryTable businessId={businessId} /> {/* ✅ Pass correct ID */}
    </div>
  );
};

export default ChatHistory;
