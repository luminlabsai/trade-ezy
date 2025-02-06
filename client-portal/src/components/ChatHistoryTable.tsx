import { useState, useEffect } from "react";
import { fetchChatHistory } from "../api/chathistory";
import { format } from "date-fns";
import { Dialog } from "@radix-ui/react-dialog";

interface ChatMessage {
    message_id: number;
    business_id: string;
    sender_id: string;
    role: string;
    content: string;
    timestamp: string;
    message_type: string;
    name: string | null;
}

const ChatHistoryTable: React.FC<{ businessId: string }> = ({ businessId }) => {
    const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
    const [selectedMessage, setSelectedMessage] = useState<ChatMessage | null>(null);
    const [fromDate, setFromDate] = useState<string>("");
    const [toDate, setToDate] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(false);

    useEffect(() => {
        loadChatHistory();
    }, [businessId, fromDate, toDate]);

    const loadChatHistory = async () => {
        setLoading(true);
        try {
            const data = await fetchChatHistory(businessId, fromDate, toDate);
            setChatHistory(data as ChatMessage[]);
        } catch (error) {
            console.error("Failed to fetch chat history", error);
        }
        setLoading(false);
    };

    return (
        <div className="p-4">
            <h2 className="text-xl font-semibold mb-4">Chat History</h2>
            <div className="flex gap-4 mb-4">
                <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="border p-2" />
                <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="border p-2" />
                <button className="px-4 py-2 bg-blue-500 text-white rounded" onClick={loadChatHistory}>Filter</button>
            </div>
            <table className="w-full border-collapse border border-gray-200">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Role</th>
                        <th>Message</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {chatHistory.map((message) => (
                        <tr key={message.message_id}>
                            <td>{format(new Date(message.timestamp), "yyyy-MM-dd HH:mm")}</td>
                            <td>{message.role}</td>
                            <td className="truncate max-w-sm">{message.content}</td>
                            <td>
                                <button className="px-3 py-1 bg-gray-500 text-white rounded" onClick={() => setSelectedMessage(message)}>View</button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            {selectedMessage && (
                <Dialog open={true} onOpenChange={() => setSelectedMessage(null)}>
                    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50">
                        <div className="bg-white p-6 rounded-lg shadow-lg">
                            <h3 className="text-lg font-bold">Message Details</h3>
                            <p><strong>Timestamp:</strong> {selectedMessage.timestamp}</p>
                            <p><strong>Role:</strong> {selectedMessage.role}</p>
                            <p><strong>Content:</strong> {selectedMessage.content}</p>
                            <button className="mt-4 px-4 py-2 bg-red-500 text-white rounded" onClick={() => setSelectedMessage(null)}>Close</button>
                        </div>
                    </div>
                </Dialog>
            )}
        </div>
    );
};

export default ChatHistoryTable;
