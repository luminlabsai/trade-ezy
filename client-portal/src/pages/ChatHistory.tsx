import React from "react";
import ChatHistoryTable from "../components/ChatHistoryTable";
import { useAuth } from "../context/AuthContext"; // ✅ Ensure correct import


const ChatHistory: React.FC = () => {
  const { businessId } = useAuth(); // ✅ Get businessId from context

  // console.log("🛠️ Business ID:", businessId); // ✅ Debugging log

  if (!businessId) {
    return <div>Loading business data...</div>; // Prevents API call with undefined ID
  }

  return (
    <div>
      <ChatHistoryTable businessId={businessId} /> {/* ✅ Pass correct ID */}
    </div>
  );
};

export default ChatHistory;
