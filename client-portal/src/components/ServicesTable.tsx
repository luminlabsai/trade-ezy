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
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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

  const toggleSelection = (serviceId: string) => {
    setSelectedServices((prev) =>
      prev.includes(serviceId)
        ? prev.filter((id) => id !== serviceId)
        : [...prev, serviceId]
    );
  };

  const handleDelete = async () => {
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
