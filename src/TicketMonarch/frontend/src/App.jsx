import { BrowserRouter, Routes, Route } from "react-router-dom";
import HomePage from "./pages/Home.jsx";
import SeatSelectionPage from "./pages/SeatSelection.jsx";
import CheckoutPage from "./pages/Checkout.jsx";
import ConfirmationPage from "./pages/Confirmation.jsx";
import DevDashboard from "./pages/DevDashboard.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/seats/:concertId" element={<SeatSelectionPage />} />
        <Route path="/checkout" element={<CheckoutPage />} />
        <Route path="/confirm" element={<ConfirmationPage />} />
        <Route path="/dev" element={<DevDashboard />} />
      </Routes>
    </BrowserRouter>
  );
}
