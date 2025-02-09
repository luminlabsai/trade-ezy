import React, { useState, useEffect } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  CircularProgress,
  Grid,
  TextField,
  Button,
  Pagination,
} from "@mui/material";
import { fetchBookings } from "../api/bookings";
import { format } from "date-fns";
import { useAuth } from "../context/AuthContext"; // Import the context hook

interface Booking {
  booking_id: string;
  service_name: string;
  duration_minutes: number;
  preferred_date_time: string;
  notes: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
}

const Bookings: React.FC = () => {
  const { businessId } = useAuth(); // Access businessId from context

  // State variables
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [fromDate, setFromDate] = useState<string>(""); // Stores the 'from' date filter
  const [toDate, setToDate] = useState<string>(""); // Stores the 'to' date filter
  const [page, setPage] = useState<number>(1); // Current page for pagination
  const [totalCount, setTotalCount] = useState<number>(0); // Total number of bookings
  const rowsPerPage = 10; // Number of rows per page

  // Trigger the API call when businessId, filters, or page changes
  useEffect(() => {
    if (businessId) {
      loadBookings();
    }
  }, [businessId, fromDate, toDate, page]);

  // Function to load bookings from the API
  const loadBookings = async () => {
    if (!businessId) {
      // console.error("Business ID is missing.");
      return;
    }

    setLoading(true);
    try {
      /* console.log("Calling fetchBookings with params:", {
        businessId,
        fromDate,
        toDate,
        rowsPerPage,
        offset: (page - 1) * rowsPerPage,
      }); */
      const response = await fetchBookings(
        businessId,
        rowsPerPage,
        (page - 1) * rowsPerPage,
        fromDate || undefined,
        toDate || undefined
      );

      // console.log("API Response:", response); // Debug the response

      if (Array.isArray(response)) {
        setBookings(response); // If the response itself is an array
        setTotalCount(response.length); // Set total count based on array length
      } else {
        setBookings(response.bookings || []); // Ensure bookings array is updated
        setTotalCount(response.totalCount || 0); // Handle undefined totalCount
      }

      // console.log("Updated bookings state:", response.bookings || response);
    } catch (error) {
      // console.error("Failed to fetch bookings:", error);
      setBookings([]);
      setTotalCount(0);
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
        Bookings
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
            onChange={(e) => setFromDate(e.target.value)} // Update 'fromDate' state
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
            onChange={(e) => setToDate(e.target.value)} // Update 'toDate' state
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
        <Grid item xs={12} sm={2}>
          <Button
            variant="contained"
            fullWidth
            size="large"
            onClick={loadBookings} // Trigger the API call manually
          >
            Filter
          </Button>
        </Grid>
      </Grid>

      {loading ? (
        <Grid container justifyContent="center" alignItems="center">
          <CircularProgress />
        </Grid>
      ) : (
        <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: "#f4f4f4" }}>
                <TableCell sx={{ fontWeight: "bold" }}>Service Name</TableCell>
                <TableCell sx={{ fontWeight: "bold" }}>Duration</TableCell>
                <TableCell sx={{ fontWeight: "bold" }}>Preferred Date/Time</TableCell>
                <TableCell sx={{ fontWeight: "bold" }}>Notes</TableCell>
                <TableCell sx={{ fontWeight: "bold" }}>Name</TableCell>
                <TableCell sx={{ fontWeight: "bold" }}>Email</TableCell>
                <TableCell sx={{ fontWeight: "bold" }}>Phone</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {bookings.length > 0 ? (
                bookings.map((booking) => (
                  <TableRow key={booking.booking_id} hover>
                    <TableCell>{booking.service_name}</TableCell>
                    <TableCell>{booking.duration_minutes} mins</TableCell>
                    <TableCell>
                      {format(new Date(booking.preferred_date_time), "yyyy-MM-dd HH:mm")}
                    </TableCell>
                    <TableCell>{booking.notes || "N/A"}</TableCell>
                    <TableCell>{booking.customer_name}</TableCell>
                    <TableCell>{booking.customer_email}</TableCell>
                    <TableCell>{booking.customer_phone}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    No bookings found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Grid container justifyContent="center" sx={{ mt: 2 }}>
        <Pagination
          count={Math.ceil(totalCount / rowsPerPage)} // Calculate total pages
          page={page}
          onChange={(_, value) => setPage(value)} // Update 'page' state on change
          color="primary"
        />
      </Grid>
    </Paper>
  );
};

export default Bookings;
