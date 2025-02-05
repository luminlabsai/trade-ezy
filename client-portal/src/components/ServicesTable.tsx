import React, { useEffect, useState } from "react";
import { fetchServices, deleteSelectedServices } from "../api/services";
import { useAuth } from "../context/AuthContext";

import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Checkbox,
  Button,
  Typography,
  TextField,
} from "@mui/material";

console.log("✅ ServicesTable.tsx is being used!");

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
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [editingServiceId, setEditingServiceId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Partial<Service>>({});

  useEffect(() => {
    console.log("Fetching services for businessId:", businessId);
    if (businessId) {
      fetchServices(businessId)
        .then((data) => {
          console.log("✅ Fetched Services:", data);
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

  console.log("Rendering ServicesTable with services:", services);

  const toggleSelection = (serviceId: string) => {
    console.log("Toggling selection for serviceId:", serviceId);
    setSelectedServices((prev) =>
      prev.includes(serviceId)
        ? prev.filter((id) => id !== serviceId)
        : [...prev, serviceId]
    );
  };

  const handleEdit = (service: Service) => {
    console.log("Editing Service:", service.service_id);
    setEditingServiceId(service.service_id);
    setEditValues({ ...service });
  };

  const handleSave = () => {
    console.log("Saving Service:", editingServiceId, editValues);
    setServices((prev) =>
      prev.map((service) =>
        service.service_id === editingServiceId ? { ...service, ...editValues } : service
      )
    );
    setEditingServiceId(null);
  };

  const handleDelete = async () => {
    console.log("Deleting services:", selectedServices);
    if (selectedServices.length > 0) {
      const confirmation = window.prompt(
        `Type "delete" to confirm removing ${selectedServices.length} services:`
      );

      if (confirmation === "delete") {
        await deleteSelectedServices(selectedServices);
        setServices((prev) => prev.filter((s) => !selectedServices.includes(s.service_id)));
        setSelectedServices([]);
      }
    }
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
              <TableCell padding="checkbox">
                <Checkbox
                  onChange={(e) => {
                    setSelectedServices(e.target.checked ? services.map((s) => s.service_id) : []);
                  }}
                  checked={selectedServices.length === services.length && services.length > 0}
                />
              </TableCell>
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
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selectedServices.includes(service.service_id)}
                      onChange={() => toggleSelection(service.service_id)}
                    />
                  </TableCell>
                  <TableCell>{service.service_name}</TableCell>
                  <TableCell>{service.description}</TableCell>
                  <TableCell align="center">{service.duration_minutes}</TableCell>
                  <TableCell align="center">${service.price.toFixed(2)}</TableCell>
                  <TableCell align="center">
                    {editingServiceId === service.service_id ? (
                      <Button onClick={handleSave}>Save</Button>
                    ) : (
                      <Button onClick={() => handleEdit(service)} disabled={editingServiceId !== null}>
                        Edit
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No services found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <Button
        onClick={handleDelete}
        disabled={selectedServices.length === 0}
        variant="contained"
        color="error"
        sx={{ mt: 2 }}
      >
        Delete Selected Services
      </Button>
    </div>
  );
};

export default ServicesTable;
