import { createContext, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'
import {
  cancelReservation as cancelReservationApi,
  createReservation,
  getReservations,
} from '../api/reservationApi'

const ReservationContext = createContext(null)

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

  const addReservation = async (paymentMethod, options = {}) => {
    const reservation = await createReservation(
      paymentMethod || '신용카드 (**** **** **** 1234)',
      options,
    )

    setReservations((prev) => [reservation, ...prev])

    return reservation
  }

  const cancelReservation = async (id) => {
    const updated = await cancelReservationApi(id)

    setReservations((prev) =>
      prev.map((reservation) =>
        reservation.id === id ? updated : reservation
      )
    )

    return updated
  }

  return (
    <ReservationContext.Provider
      value={{
        reservations,
        addReservation,
        cancelReservation,
      }}
    >
      {children}
    </ReservationContext.Provider>
  )
}

export function useReservations() {
  const ctx = useContext(ReservationContext)

  if (!ctx) {
    throw new Error(
      'useReservations must be used within ReservationProvider'
    )
  }

  return ctx
}
