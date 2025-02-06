import React, { useState, useEffect } from "react";
import { fetchChatHistory } from "../api/chathistory";
import { format } from "date-fns";
import { Table, TableHead, TableBody, TableRow, TableCell } from "@mui/material";
import Pagination from "@mui/material/Pagination";

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
    const [fromDate, setFromDate] = useState<string>("");
    const [toDate, setToDate] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(false);
    const [page, setPage] = useState<number>(1);
    const rowsPerPage = 10;

    useEffect(() => {
        loadChatHistory();
    }, [businessId, fromDate, toDate, page]);

    const loadChatHistory = async () => {
        setLoading(true);
        try {
            const data = await fetchChatHistory(businessId, fromDate, toDate, rowsPerPage, (page - 1) * rowsPerPage);
            setChatHistory(data as ChatMessage[]);
        } catch (error) {
            console.error("Failed to fetch chat history", error);
        }
        setLoading(false);
    };

    return (
        <div className="p-4 h-screen flex flex-col">
            <h2 className="text-xl font-semibold mb-4">Chat History</h2>
            <div className="flex gap-4 mb-4">
                <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="border p-2" />
                <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="border p-2" />
                <button className="px-4 py-2 bg-blue-500 text-white rounded" onClick={loadChatHistory}>Filter</button>
            </div>
            <div className="flex-grow overflow-auto">
                <Table className="w-full border border-gray-300">
                    <TableHead>
                        <TableRow className="border-b border-gray-300">
                            <TableCell>Timestamp</TableCell>
                            <TableCell>Role</TableCell>
                            <TableCell>Message</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {chatHistory.map((message) => (
                            <TableRow key={message.message_id} className="border-b border-gray-300">
                                <TableCell>{format(new Date(message.timestamp), "yyyy-MM-dd HH:mm")}</TableCell>
                                <TableCell>{message.role}</TableCell>
                                <TableCell className="truncate max-w-sm">{message.content}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
            <div className="flex justify-center mt-4">
                <Pagination count={Math.ceil(chatHistory.length / rowsPerPage)} page={page} onChange={(_, value) => setPage(value)} color="primary" />
            </div>
        </div>
    );
};

export default ChatHistoryTable;