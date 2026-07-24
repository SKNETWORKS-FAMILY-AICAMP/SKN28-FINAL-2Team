import { Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import ItineraryPage from './pages/ItineraryPage.jsx'
import ReviewPage from './pages/ReviewPage.jsx'
import BookingPage from './pages/BookingPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/itinerary" element={<ItineraryPage />} />
      <Route path="/review" element={<ReviewPage />} />
      <Route path="/booking" element={<BookingPage />} />
    </Routes>
  )
}
