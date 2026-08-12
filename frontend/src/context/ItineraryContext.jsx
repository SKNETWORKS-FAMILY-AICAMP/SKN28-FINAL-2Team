import { createContext, useContext, useEffect, useState } from 'react'
import {
  getItineraries,
  deleteItinerary,
  patchItinerary,
  regenerateItinerary,
  reviseItinerary,
  getRoute,
} from '../api/itinerary'
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

  // 채팅으로 일정 수정 (또는 추천만 조회)
  async function revise(id, message) {
    const result = await reviseItinerary(id, message)

    if (result.mode === 'edit') {
      await loadItineraries()
    }

    return result
  }

  async function fetchRoute(id) {
    return await getRoute(id)
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
        revise,
        fetchRoute,
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