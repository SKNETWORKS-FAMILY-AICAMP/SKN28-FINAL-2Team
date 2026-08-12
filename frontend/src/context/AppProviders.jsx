import { AuthProvider } from './AuthContext.jsx'
import { BookmarkProvider } from './BookmarkContext.jsx'
import { ReservationProvider } from './ReservationContext.jsx'
import { ItineraryProvider } from './ItineraryContext.jsx'
import { CartProvider } from './CartContext.jsx'
import CartWidget from '../components/CartWidget.jsx'

export default function AppProviders({ children }) {
  return (
    <AuthProvider>
      <BookmarkProvider>
        <ReservationProvider>
          <ItineraryProvider>
            <CartProvider>
              {children}
              <CartWidget />
            </CartProvider>
          </ItineraryProvider>
        </ReservationProvider>
      </BookmarkProvider>
    </AuthProvider>
  )
}