import React, { useState, useEffect } from "react";
import { fetchChatHistory } from "../api/chathistory";
import { format } from "date-fns";
import {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Paper,
  Button,
  Typography,
  TextField,
  Pagination,
  Tooltip,
  Grid,
} from "@mui/material";

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
  const [totalCount, setTotalCount] = useState<number>(0);
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
      const response = await fetchChatHistory(
        businessId,
        fromDate,
        toDate,
        rowsPerPage,
        (page - 1) * rowsPerPage
      );
      setChatHistory(response.messages);
      setTotalCount(response.totalCount);
    } catch (error) {
      console.error("Failed to fetch chat history", error);
    }
    setLoading(false);
  };

  return (
    <Paper
      sx={{
        padding: 2,
        marginTop: 2,
        borderRadius: 2,
        boxShadow: 3,
        width: "100%",
      }}
    >
      <Typography variant="h5" sx={{ mb: 2 }}>
        Chat History
      </Typography>

      {/* Date Filters */}
      <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <Grid item xs={12} sm={5}>
          <TextField
            label="From Date"
            type="date"
            fullWidth
            size="small"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
        <Grid item xs={12} sm={5}>
          <TextField
            label="To Date"
            type="date"
            fullWidth
            size="small"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
        <Grid item xs={12} sm={2}>
          <Button variant="contained" fullWidth size="large" onClick={loadChatHistory}>
            Filter
          </Button>
        </Grid>
      </Grid>

      {/* Chat Table */}
      <TableContainer
        component={Paper}
        sx={{ borderRadius: 2, boxShadow: 2, overflow: "hidden", width: "100%" }}
      >
        <Table size="small">
          <TableHead>
            <TableRow sx={{ backgroundColor: "#f4f4f4" }}>
              <TableCell sx={{ fontWeight: "bold" }}>Timestamp</TableCell>
              <TableCell sx={{ fontWeight: "bold" }}>Role</TableCell>
              <TableCell sx={{ fontWeight: "bold" }}>Message</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {chatHistory.length > 0 ? (
              chatHistory.map((message) => (
                <TableRow key={message.message_id} hover>
                  <TableCell>{format(new Date(message.timestamp), "yyyy-MM-dd HH:mm")}</TableCell>
                  <TableCell>{message.role}</TableCell>
                  <TableCell>
                    <Tooltip title={message.content} arrow>
                      <Typography
                        noWrap
                        sx={{
                          maxWidth: "100%",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {message.content}
                      </Typography>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={3} align="center">
                  No chat history found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      <Grid container justifyContent="center" sx={{ mt: 2 }}>
        <Pagination
          count={Math.ceil(totalCount / rowsPerPage)}
          page={page}
          onChange={(_, value) => setPage(value)}
          color="primary"
        />
      </Grid>
    </Paper>
  );
};

export default ChatHistoryTable;
