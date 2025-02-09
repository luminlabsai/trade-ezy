import React, { useEffect, useState } from "react";
import { fetchBookings } from "../api/bookings";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  Pagination,
  Grid,
  TextField,
  MenuItem,
  Select,
  InputLabel,
  FormControl,
  Button,
} from "@mui/material";

interface Booking {
  booking_id: string;
  service_name: string;
  preferred_date_time: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
}

const BookingsTable: React.FC<{ businessId: string; availableServices: string[] }> = ({ businessId, availableServices }) => {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [page, setPage] = useState<number>(1);
  const [rowsPerPage] = useState<number>(10);

  const [fromDate, setFromDate] = useState<string | undefined>();
  const [toDate, setToDate] = useState<string | undefined>();
  const [selectedService, setSelectedService] = useState<string>("");

  useEffect(() => {
    if (businessId) {
      console.log("Loading bookings..."); // Debug log
      console.log({ fromDate, toDate, page }); // Debug log of filters
      loadBookings();
    }
  }, [businessId, page, fromDate, toDate]);
  

  const loadBookings = async () => {
    setLoading(true);
    try {
      const response = await fetchBookings(
        businessId,
        rowsPerPage,
        (page - 1) * rowsPerPage,
        fromDate,
        toDate,
        selectedService || undefined
      );
      setBookings(response.bookings || []);
      setTotalCount(response.totalCount || 0);
    } catch (error) {
      console.error("Failed to fetch bookings:", error);
      setBookings([]);
      setTotalCount(0);
    }
    setLoading(false);
  };

  const handleFilterApply = () => {
    setPage(1); // Reset to first page
    loadBookings();
  };

  return (
    <Paper sx={{ padding: 2, marginTop: 2, borderRadius: 2, boxShadow: 3, width: "100%" }}>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Bookings
      </Typography>

      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid item xs={12} sm={4}>
          <TextField
            label="From Date"
            type="date"
            value={fromDate || ""}
            onChange={(e) => setFromDate(e.target.value || undefined)}
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <TextField
            label="To Date"
            type="date"
            value={toDate || ""}
            onChange={(e) => setToDate(e.target.value || undefined)}
            fullWidth
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <FormControl fullWidth>
            <InputLabel id="service-name-label">Service</InputLabel>
            <Select
              labelId="service-name-label"
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              displayEmpty
            >
              <MenuItem value="">All Services</MenuItem>
              {availableServices.map((service) => (
                <MenuItem key={service} value={service}>
                  {service}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>
        <Grid item xs={12} sm={12} sx={{ textAlign: "right" }}>
          <Button variant="contained" color="primary" onClick={handleFilterApply}>
            Apply Filters
          </Button>
        </Grid>
      </Grid>

      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ backgroundColor: "#f4f4f4" }}>
              <TableCell sx={{ fontWeight: "bold" }}>Date & Time</TableCell>
              <TableCell sx={{ fontWeight: "bold" }}>Service Name</TableCell>
              <TableCell sx={{ fontWeight: "bold" }}>Client Name</TableCell>
              <TableCell sx={{ fontWeight: "bold" }}>Client Email</TableCell>
              <TableCell sx={{ fontWeight: "bold" }}>Client Phone</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : bookings.length > 0 ? (
              bookings.map((booking) => (
                <TableRow key={booking.booking_id} hover>
                  <TableCell>{new Date(booking.preferred_date_time).toLocaleString()}</TableCell>
                  <TableCell>{booking.service_name}</TableCell>
                  <TableCell>{booking.customer_name}</TableCell>
                  <TableCell>{booking.customer_email}</TableCell>
                  <TableCell>{booking.customer_phone}</TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  No bookings found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

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

export default BookingsTable;
