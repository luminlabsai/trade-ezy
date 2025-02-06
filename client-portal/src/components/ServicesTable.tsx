import React, { useEffect, useState } from "react";
import { fetchServices, deleteService, updateService, addService } from "../api/services";
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
  const [openAddDialog, setOpenAddDialog] = useState(false);
  const [newService, setNewService] = useState<Omit<Service, "service_id">>({
    service_name: "",
    description: "",
    duration_minutes: 0,
    price: 0,
  });
  const [deleteConfirmationOpen, setDeleteConfirmationOpen] = useState(false);
  const [serviceToDelete, setServiceToDelete] = useState<string | null>(null);

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

  const handleSave = async () => {
    if (editingServiceId) {
      await updateService(editingServiceId, editValues);
      setServices((prev) =>
        prev.map((service) =>
          service.service_id === editingServiceId ? { ...service, ...editValues } : service
        )
      );
      setEditingServiceId(null);
    }
  };

  const handleDelete = async (serviceId: string) => {
    setServiceToDelete(serviceId);
    setDeleteConfirmationOpen(true);
  };

  const confirmDelete = async () => {
    if (serviceToDelete) {
      await deleteService(serviceToDelete);
      setServices((prev) => prev.filter((s) => s.service_id !== serviceToDelete));
      setDeleteConfirmationOpen(false);
      setServiceToDelete(null);
    }
  };

  const cancelDelete = () => {
    setDeleteConfirmationOpen(false);
    setServiceToDelete(null);
  };

  const handleAddService = async () => {
    if (!newService.service_name || !newService.duration_minutes || !newService.price) {
      alert("Please fill in all required fields.");
      return;
    }

    if (!businessId) {
      alert("Business ID is missing. Cannot add service.");
      return;
    }

    try {
      const addedService = await addService(businessId, newService);

      if (!addedService || !addedService.service_id) {
        alert("Service addition failed. Try again.");
        return;
      }

      const updatedServices = await fetchServices(businessId);
      setServices(updatedServices);

      setNewService({
        service_name: "",
        description: "",
        duration_minutes: 0,
        price: 0,
      });
      setOpenAddDialog(false);
    } catch (error) {
      console.error("🚨 Failed to add service:", error);
      alert("Failed to add service. Please try again.");
    }
  };

  const handleCloseDialog = () => {
    setOpenAddDialog(false);
    setTimeout(() => {
      if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
      }
    }, 0);
  };

  if (loading) return <Typography>Loading services...</Typography>;
  if (error) return <Typography color="error">{error}</Typography>;

  return (
    <div style={{ padding: "20px" }}>
      <Typography variant="h5" gutterBottom>
        Services
      </Typography>
      <Button variant="contained" color="primary" onClick={() => setOpenAddDialog(true)}>
        Add Service
      </Button>
      <TableContainer component={Paper} sx={{ borderRadius: 2, overflow: "hidden", boxShadow: 3, mt: 2 }}>
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
                      `$${(service.price || 0).toFixed(2)}`
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
      <Dialog
        open={openAddDialog}
        onClose={handleCloseDialog}
        disableEnforceFocus
        disableRestoreFocus
        keepMounted
      >
        <DialogTitle>Add New Service</DialogTitle>
        <DialogContent>
          <TextField label="Service Name" fullWidth margin="dense" value={newService.service_name} onChange={(e) => setNewService({ ...newService, service_name: e.target.value })} />
          <TextField label="Description" fullWidth margin="dense" value={newService.description} onChange={(e) => setNewService({ ...newService, description: e.target.value })} />
          <TextField label="Duration (mins)" type="number" fullWidth margin="dense" value={newService.duration_minutes} onChange={(e) => setNewService({ ...newService, duration_minutes: Number(e.target.value) })} />
          <TextField label="Price ($)" type="number" fullWidth margin="dense" value={newService.price} onChange={(e) => setNewService({ ...newService, price: Number(e.target.value) })} />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleAddService} color="primary">Add</Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={deleteConfirmationOpen}
        onClose={cancelDelete}
        aria-labelledby="delete-confirmation-dialog-title"
      >
        <DialogTitle id="delete-confirmation-dialog-title">Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography>Are you sure you want to delete this service?</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={cancelDelete} color="primary">
            Cancel
          </Button>
          <Button onClick={confirmDelete} color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default ServicesTable;