import { createContext, useContext, useState } from 'react'

const ReservationContext = createContext(null)

// 백엔드 GET/POST /api/reservations/ 응답 형태와 필드명을 맞춤
export function ReservationProvider({ children }) {
  const [reservations, setReservations] = useState([])

  const addReservation = (items, paymentMethod) => {
    const totalPrice = items.reduce((sum, item) => sum + item.price, 0)
    const reservation = {
      id: Date.now(),
      items,
      totalPrice,
      paymentMethod: paymentMethod || '신용카드 (**** **** **** 1234)',
      status: 'confirmed',
      statusDisplay: '확정',
      createdAt: new Date().toISOString(),
    }
    setReservations((prev) => [reservation, ...prev])
    return reservation
  }

  return (
    <ReservationContext.Provider value={{ reservations, addReservation }}>
      {children}
    </ReservationContext.Provider>
  )
}

export function useReservations() {
  const ctx = useContext(ReservationContext)
  if (!ctx) throw new Error('useReservations must be used within ReservationProvider')
  return ctx
}
