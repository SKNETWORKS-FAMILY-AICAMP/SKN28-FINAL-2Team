import { createContext, useContext, useEffect, useState } from 'react'
import { getItineraries, deleteItinerary, patchItinerary, regenerateItinerary, } from '../api/itinerary'
import { useAuth } from './AuthContext'

const ItineraryContext = createContext(null)

export function ItineraryProvider({ children }) {
  const [itineraries, setItineraries] = useState([])
  const [loading, setLoading] = useState(true)
  const { isLoggedIn, loading: authLoading } = useAuth()

  useEffect(() => {
    if (authLoading) return

    if (!isLoggedIn) {
      setItineraries([])
      setLoading(false)
      return
    }

    loadItineraries()
  }, [isLoggedIn, authLoading])

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

  async function patch(id, data) {
    const result = await patchItinerary(id, data)
    await loadItineraries()
    return result
  }

  async function regenerate(id) {
    const result = await regenerateItinerary(id)
    await loadItineraries()
    return result
  }

  return (
    <ItineraryContext.Provider
      value={{
        itineraries,
        loading,
        refresh: loadItineraries,
        removeItinerary,
        patch,
        regenerate,
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