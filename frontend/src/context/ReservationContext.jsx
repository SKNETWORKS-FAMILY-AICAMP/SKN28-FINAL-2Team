import { createContext, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'
import { createReservation, getReservations } from '../api/reservationApi'

const ReservationContext = createContext(null)

// 백엔드 GET/POST /api/reservations/ 응답 형태와 필드명을 맞춤
export function ReservationProvider({ children }) {
  const { user, loading } = useAuth()

  const [reservations, setReservations] = useState([])

  const loadReservations = async () => {
    try {
      const data = await getReservations()

      setReservations(
        Array.isArray(data) ? data : data.results || []
      )
    } catch (error) {
      console.error('예약 목록 조회 실패:', error)
    }
  }

  useEffect(() => {
    if (loading) return

    if (!user) {
      setReservations([])
      return
    }

    loadReservations()
  }, [loading, user])

  const addReservation = async (items, paymentMethod) => {
    const packageIds = items.map((item) => item.packageId)

    const reservation = await createReservation(
      packageIds,
      paymentMethod || '신용카드 (**** **** **** 1234)'
    )

    setReservations((prev) => [reservation, ...prev])

    return reservation
  }

  return (
    <ReservationContext.Provider
      value={{
        reservations,
        addReservation,
      }}
    >
      {children}
    </ReservationContext.Provider>
  )
}

export function useReservations() {
  const ctx = useContext(ReservationContext)
  if (!ctx) throw new Error('useReservations must be used within ReservationProvider')
  return ctx
}