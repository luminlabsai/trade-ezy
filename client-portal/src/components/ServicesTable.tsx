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
      setNewService({ service_name: "", description: "", duration_minutes: 0, price: 0 });
      setOpenAddDialog(false);
    } catch (error) {
      console.error("🚨 Failed to add service:", error);
      alert("Failed to add service. Please try again.");
    }
  };

  if (loading) return <Typography>Loading services...</Typography>;
  if (error) return <Typography color="error">{error}</Typography>;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "20px" }}>
      <Typography variant="h5" gutterBottom>
        Services
      </Typography>
      <Button variant="contained" onClick={() => setOpenAddDialog(true)}>Add Service</Button>
      <TableContainer component={Paper} sx={{ flexGrow: 1, mt: 2 }}>
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
                  <TableCell>{service.service_name}</TableCell>
                  <TableCell>{service.description}</TableCell>
                  <TableCell align="center">{service.duration_minutes}</TableCell>
                  <TableCell align="center">${(service.price || 0).toFixed(2)}</TableCell>
                  <TableCell align="center">
                    <Button onClick={() => handleEdit(service)}>Edit</Button>
                    <Button onClick={() => handleDelete(service.service_id)} color="error">Delete</Button>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={5} align="center">No services found.</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </div>
  );
};

export default ServicesTable;
