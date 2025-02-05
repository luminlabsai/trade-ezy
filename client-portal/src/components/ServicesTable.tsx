import React, { useEffect, useState } from "react";
import { fetchServices, deleteService, updateService } from "../api/services";
import { useAuth } from "../context/AuthContext";
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
  DialogContentText,
  DialogTitle,
} from "@mui/material";

interface Service {
  service_id: string;
  service_name: string;
  description: string;
  duration_minutes: number;
  price: number;
}

const ServicesTable: React.FC = () => {
  const { businessId } = useAuth();
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [editingServiceId, setEditingServiceId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Partial<Service>>({});
  const [confirmAction, setConfirmAction] = useState<null | (() => void)>(null);
  const [openConfirmDialog, setOpenConfirmDialog] = useState(false);

  useEffect(() => {
    if (businessId) {
      fetchServices(businessId)
        .then((data) => {
          setServices(data);
          setLoading(false);
        })
        .catch((err) => {
          console.error("❌ Failed to fetch services:", err);
          setError("Failed to load services.");
          setLoading(false);
        });
    }
  }, [businessId]);

  const handleEdit = (service: Service) => {
    setEditingServiceId(service.service_id);
    setEditValues({ ...service });
  };

  const confirmActionHandler = (action: () => void) => {
    setConfirmAction(() => action);
    setOpenConfirmDialog(true);
  };

  const handleSave = () => {
    confirmActionHandler(async () => {
      if (editingServiceId) {
        await updateService(editingServiceId, editValues);
        setServices((prev) =>
          prev.map((service) =>
            service.service_id === editingServiceId ? { ...service, ...editValues } : service
          )
        );
        setEditingServiceId(null);
      }
    });
  };

  const handleDelete = (serviceId: string) => {
    confirmActionHandler(async () => {
      await deleteService(serviceId);
      setServices((prev) => prev.filter((s) => s.service_id !== serviceId));
    });
  };

  if (loading) return <Typography>Loading services...</Typography>;
  if (error) return <Typography color="error">{error}</Typography>;

  return (
    <div style={{ padding: "20px" }}>
      <Typography variant="h5" gutterBottom>
        Services
      </Typography>
      <TableContainer component={Paper} sx={{ borderRadius: 2, overflow: "hidden", boxShadow: 3 }}>
        <Table>
          <TableHead>
            <TableRow sx={{ backgroundColor: "#f4f4f4" }}>
              <TableCell>Service Name</TableCell>
              <TableCell>Description</TableCell>
              <TableCell align="center">Duration (mins)</TableCell>
              <TableCell align="center">Price ($)</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {services.length > 0 ? (
              services.map((service) => (
                <TableRow key={service.service_id} hover>
                  <TableCell>
                    {editingServiceId === service.service_id ? (
                      <TextField
                        value={editValues.service_name || ""}
                        onChange={(e) =>
                          setEditValues({ ...editValues, service_name: e.target.value })
                        }
                      />
                    ) : (
                      service.service_name
                    )}
                  </TableCell>
                  <TableCell>
                    {editingServiceId === service.service_id ? (
                      <TextField
                        value={editValues.description || ""}
                        onChange={(e) =>
                          setEditValues({ ...editValues, description: e.target.value })
                        }
                      />
                    ) : (
                      service.description
                    )}
                  </TableCell>
                  <TableCell align="center">
                    {editingServiceId === service.service_id ? (
                      <TextField
                        value={editValues.duration_minutes || ""}
                        onChange={(e) =>
                          setEditValues({ ...editValues, duration_minutes: Number(e.target.value) })
                        }
                        type="number"
                      />
                    ) : (
                      service.duration_minutes
                    )}
                  </TableCell>
                  <TableCell align="center">
                    {editingServiceId === service.service_id ? (
                      <TextField
                        value={editValues.price || ""}
                        onChange={(e) =>
                          setEditValues({ ...editValues, price: Number(e.target.value) })
                        }
                        type="number"
                      />
                    ) : (
                      `$${service.price.toFixed(2)}`
                    )}
                  </TableCell>
                  <TableCell align="center">
                    {editingServiceId === service.service_id ? (
                      <Button onClick={handleSave}>Save</Button>
                    ) : (
                      <Button onClick={() => handleEdit(service)}>Edit</Button>
                    )}
                    <Button onClick={() => handleDelete(service.service_id)} color="error">
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  No services found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <Dialog open={openConfirmDialog} onClose={() => setOpenConfirmDialog(false)}>
        <DialogTitle>Confirm Action</DialogTitle>
        <DialogContent>
          <DialogContentText>Are you sure you want to proceed?</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenConfirmDialog(false)}>Cancel</Button>
          <Button
            onClick={() => {
              if (confirmAction) confirmAction();
              setOpenConfirmDialog(false);
            }}
            color="primary"
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default ServicesTable;
