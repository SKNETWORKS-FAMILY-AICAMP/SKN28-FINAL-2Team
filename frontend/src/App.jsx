import { Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import ItineraryPage from './pages/ItineraryPage.jsx'
import ReviewPage from './pages/ReviewPage.jsx'
import BookingPage from './pages/BookingPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import KakaoCallback from './pages/KakaoCallback.jsx'
import MyPage from './pages/MyPage.jsx'
import MyItinerariesPage from './pages/MyItinerariesPage.jsx'
import MyBookmarksPage from './pages/MyBookmarksPage.jsx'
import MyReservationsPage from './pages/MyReservationsPage.jsx'
import RequireAuth from './context/RequireAuth.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/itinerary" element={<ItineraryPage />} />
      <Route path="/review" element={<ReviewPage />} />
      <Route path="/booking" element={<BookingPage />} />

      <Route path="/login" element={<LoginPage />} />
      <Route path="/oauth/kakao/callback" element={<KakaoCallback />} />

      <Route
        path="/mypage"
        element={
          <RequireAuth>
            <MyPage />
          </RequireAuth>
        }
      />
      <Route
        path="/my/itineraries"
        element={
          <RequireAuth>
            <MyItinerariesPage />
          </RequireAuth>
        }
      />
      <Route
        path="/my/bookmarks"
        element={
          <RequireAuth>
            <MyBookmarksPage />
          </RequireAuth>
        }
      />
      <Route
        path="/my/reservations"
        element={
          <RequireAuth>
            <MyReservationsPage />
          </RequireAuth>
        }
      />
    </Routes>
  )
}
