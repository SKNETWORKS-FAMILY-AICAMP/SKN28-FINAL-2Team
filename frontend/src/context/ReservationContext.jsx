import { createContext, useContext, useEffect, useState } from 'react'
import {
  cancelReservation as cancelReservationApi,
  createReservation,
  getReservations,
} from '../api/reservationApi'

const ReservationContext = createContext(null)

export function ReservationProvider({ children }) {
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
    loadReservations()
  }, [])

  const addReservation = async (items, paymentMethod) => {
    const packageIds = items.map((item) => item.packageId)

    const reservation = await createReservation(
      packageIds,
      paymentMethod || '신용카드 (**** **** **** 1234)'
    )

    setReservations((prev) => [reservation, ...prev])

    return reservation
  }

  const cancelReservation = async (id) => {
    const updated = await cancelReservationApi(id)

    setReservations((prev) =>
      prev.map((r) => (r.id === id ? updated : r))
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