import { createContext, useContext, useEffect, useState } from 'react'
import {
  getItineraries,
  deleteItinerary,
} from '../api/itinerary'

const ItineraryContext = createContext(null)

export function ItineraryProvider({ children }) {
  const [itineraries, setItineraries] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadItineraries()
  }, [])

  async function loadItineraries() {
    try {
      const data = await getItineraries()
      setItineraries(data)
    } catch (err) {
      console.error('일정 조회 실패', err)
    } finally {
      setLoading(false)
    }
  }

  async function removeItinerary(id) {
    await deleteItinerary(id)

    setItineraries((prev) =>
      prev.filter((itinerary) => itinerary.id !== id)
    )
  }

  return (
    <ItineraryContext.Provider
      value={{
        itineraries,
        loading,
        refresh: loadItineraries,
        removeItinerary,
      }}
    >
      {children}
    </ItineraryContext.Provider>
  )
}

export function useItineraries() {
  const ctx = useContext(ItineraryContext)

  if (!ctx) {
    throw new Error(
      'useItineraries must be used within ItineraryProvider'
    )
  }

  return ctx
}