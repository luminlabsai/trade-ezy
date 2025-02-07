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

  const handleSave = async () => {
    try {
      console.log("📡 Saving account changes:", formData);
      await onSave(formData);
      setSnackbarOpen(true);
      setEditDialogOpen(false);
    } catch (error) {
      console.error("❌ Failed to update account data:", error);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", width: "100%", padding: "20px" }}>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: "bold" }}>Account Details</Typography>

      <TableContainer component={Paper} sx={{ flex: 1, borderRadius: 2, overflow: "hidden", boxShadow: 2 }}>
        <Table size="medium">
          <TableBody>
            <TableRow>
              <TableCell><Typography fontWeight="bold">Business Name</Typography></TableCell>
              <TableCell>{name}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><Typography fontWeight="bold">Address</Typography></TableCell>
              <TableCell>{address}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><Typography fontWeight="bold">Phone</Typography></TableCell>
              <TableCell>{phone}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><Typography fontWeight="bold">Email</Typography></TableCell>
              <TableCell>{email}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell><Typography fontWeight="bold">Description</Typography></TableCell>
              <TableCell>{description}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>

      <Button variant="contained" color="primary" sx={{ mt: 2, alignSelf: "flex-end" }} onClick={() => setEditDialogOpen(true)}>
        Edit Account
      </Button>

      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Edit Account Details</DialogTitle>
        <DialogContent>
          <TextField label="Address" fullWidth margin="dense" name="address" value={formData.address} onChange={handleChange} />
          <TextField label="Phone" fullWidth margin="dense" name="phone" value={formData.phone} onChange={handleChange} />
          <TextField label="Email" fullWidth margin="dense" name="email" value={formData.email} onChange={handleChange} />
          <TextField label="Description" fullWidth margin="dense" name="description" value={formData.description} onChange={handleChange} multiline />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSave} color="primary">Save Changes</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbarOpen} autoHideDuration={3000} onClose={() => setSnackbarOpen(false)}>
        <Alert onClose={() => setSnackbarOpen(false)} severity="success">
          ✅ Account details updated successfully!
        </Alert>
      </Snackbar>
    </div>
  );
};

export default AccountTable;
