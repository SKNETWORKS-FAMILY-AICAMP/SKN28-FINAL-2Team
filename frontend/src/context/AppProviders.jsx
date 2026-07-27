import { AuthProvider } from './AuthContext.jsx'
import { BookmarkProvider } from './BookmarkContext.jsx'
import { ReservationProvider } from './ReservationContext.jsx'
import { ItineraryProvider } from './ItineraryContext.jsx'

export default function AppProviders({ children }) {
  return (
    <AuthProvider>
      <BookmarkProvider>
        <ReservationProvider>
          <ItineraryProvider>{children}</ItineraryProvider>
        </ReservationProvider>
      </BookmarkProvider>
    </AuthProvider>
  )
}
