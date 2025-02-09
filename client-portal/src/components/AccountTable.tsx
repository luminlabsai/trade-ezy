import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Typography,
  TextField,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Snackbar,
  Alert,
} from "@mui/material";

interface AccountProps {
  name: string;
  address: string;
  phone: string;
  email: string;
  operating_hours: Record<string, { open: string; close: string } | null>;
  description: string;
  onSave: (updatedData: any) => void;
}

const daysOfWeek = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const AccountTable: React.FC<AccountProps> = ({
  name,
  address,
  phone,
  email,
  operating_hours,
  description,
  onSave,
}) => {
  const [formData, setFormData] = useState({ address, phone, email, description, operating_hours });
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleHoursChange = (day: string, field: "open" | "close", value: string) => {
    setFormData((prev) => ({
      ...prev,
      operating_hours: {
        ...prev.operating_hours,
        [day]: prev.operating_hours[day] ? { ...prev.operating_hours[day], [field]: value } : null,
      },
    }));
  };

  const toggleClosed = (day: string) => {
    setFormData((prev) => ({
      ...prev,
      operating_hours: {
        ...prev.operating_hours,
        [day]: prev.operating_hours[day] ? null : { open: "08:00", close: "16:00" },
      },
    }));
  };

  const handleSave = async () => {
    try {
      console.log("📡 Saving account changes:", formData);
      await onSave(formData);

      setSnackbarOpen(true); // ✅ Show success notification
      setEditDialogOpen(false);
    } catch (error) {
      console.error("❌ Failed to update account data:", error);
    }
  };

  return (
    <div style={{ padding: "0px" }}> {/* Removed extra padding */}
      <Typography variant="h6" sx={{ mb: 1 }}>
        Account Details
      </Typography>

      <TableContainer component={Paper} sx={{ borderRadius: 2, overflow: "hidden", boxShadow: 2, margin: 0 }}>
        <Table size="small">
          <TableBody>
            <TableRow>
              <TableCell sx={{ fontWeight: "bold" }}>Business Name</TableCell>
              <TableCell>{name}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: "bold" }}>Address</TableCell>
              <TableCell>{address}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: "bold" }}>Phone</TableCell>
              <TableCell>{phone}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: "bold" }}>Email</TableCell>
              <TableCell>{email}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: "bold" }}>Description</TableCell>
              <TableCell>{description}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>

      <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
        Operating Hours
      </Typography>
      <TableContainer component={Paper} sx={{ borderRadius: 2, overflow: "hidden", boxShadow: 2, margin: 0 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ backgroundColor: "#f4f4f4" }}>
              <TableCell>Day</TableCell>
              <TableCell>Open Time</TableCell>
              <TableCell>Close Time</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {daysOfWeek.map((day) => (
              <TableRow key={day}>
                <TableCell>{day}</TableCell>
                <TableCell>{operating_hours[day]?.open || "Closed"}</TableCell>
                <TableCell>{operating_hours[day]?.close || "Closed"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Button variant="contained" color="primary" sx={{ mt: 2 }} onClick={() => setEditDialogOpen(true)}>
        Edit Account
      </Button>

      {/* EDIT POPUP (DIALOG) */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle sx={{ fontSize: "1.1rem", paddingBottom: "8px" }}>Edit Account Details</DialogTitle>
        <DialogContent sx={{ pb: 1, padding: "12px" }}>
          <TextField
            label="Address"
            fullWidth
            margin="dense"
            size="small"
            sx={{ mb: 0.5 }}
            name="address"
            value={formData.address}
            onChange={handleChange}
          />
          <TextField
            label="Phone"
            fullWidth
            margin="dense"
            size="small"
            sx={{ mb: 0.5 }}
            name="phone"
            value={formData.phone}
            onChange={handleChange}
          />
          <TextField
            label="Email"
            fullWidth
            margin="dense"
            size="small"
            sx={{ mb: 0.5 }}
            name="email"
            value={formData.email}
            onChange={handleChange}
          />
          <TextField
            label="Description"
            fullWidth
            multiline
            margin="dense"
            size="small"
            sx={{ mb: 0.5 }}
            name="description"
            value={formData.description}
            onChange={handleChange}
          />

          <Typography variant="h6" sx={{ mt: 1.5, mb: 0.5, fontSize: "1rem" }}>Operating Hours</Typography>
          {daysOfWeek.map((day) => (
            <div key={day} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
              <Typography sx={{ minWidth: "80px", fontSize: "0.9rem" }}>{day}</Typography>

              <TextField
                type="time"
                value={formData.operating_hours[day]?.open || ""}
                onChange={(e) => handleHoursChange(day, "open", e.target.value)}
                disabled={!formData.operating_hours[day]}
                margin="dense"
                size="small"
                sx={{ width: "110px" }}
              />

              <TextField
                type="time"
                value={formData.operating_hours[day]?.close || ""}
                onChange={(e) => handleHoursChange(day, "close", e.target.value)}
                disabled={!formData.operating_hours[day]}
                margin="dense"
                size="small"
                sx={{ width: "110px" }}
              />

              <Button
                variant="contained"
                size="small"
                sx={{ minWidth: "70px", fontSize: "0.75rem", padding: "3px 6px" }}
                onClick={() => toggleClosed(day)}
              >
                {formData.operating_hours[day] ? "Close" : "Open"}
              </Button>
            </div>
          ))}
        </DialogContent>
        <DialogActions sx={{ padding: "8px 16px" }}>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSave} color="primary">Save Changes</Button>
        </DialogActions>
      </Dialog>

      {/* ✅ Snackbar Notification */}
      <Snackbar open={snackbarOpen} autoHideDuration={3000} onClose={() => setSnackbarOpen(false)}>
        <Alert onClose={() => setSnackbarOpen(false)} severity="success">
          ✅ Account details updated successfully!
        </Alert>
      </Snackbar>
    </div>
  );
};

export default AccountTable;
