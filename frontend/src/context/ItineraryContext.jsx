import { createContext, useContext, useEffect, useState } from 'react'
import { getItineraries, createItinerary, updateItinerary, patchItinerary, 
  deleteItinerary, regenerateItinerary, reviseItinerary, getRoute } from '../api/itinerary'
import { useAuth } from './AuthContext'

const ItineraryContext = createContext(null);

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

    loadItineraries().catch((err) => {
      console.error('초기 일정 조회 실패', err)
    })
  }, [isLoggedIn, authLoading])

  async function loadItineraries() {
    setLoading(true)
    try {
      const data = await getItineraries();
      setItineraries(data);
    } catch (err) {
      console.error('일정 조회 실패', err)
      throw err
    } finally {
      setLoading(false);
    }
  }

  // 일정 생성
  async function create(data) {
    const result = await createItinerary(data);
    await loadItineraries();
    return result;
  }

  // 일정 전체 수정
  async function update(id, data) {
    const result = await updateItinerary(id, data);
    await loadItineraries();
    return result;
  }

  // 일정 일부 수정
  async function patch(id, data) {
    const result = await patchItinerary(id, data);
    await loadItineraries();
    return result;
  }

  // 일정 삭제
  async function remove(id) {
    await deleteItinerary(id);
    await loadItineraries();
  }

  // 일정 재생성
  async function regenerate(id) {
    const result = await regenerateItinerary(id);
    await loadItineraries();
    return result;
  }

// 채팅으로 일정 수정 (또는 추천만 조회)
  async function revise(id, message) {
    const result = await reviseItinerary(id, message);

    // 일정이 실제로 바뀌었을 때만 목록을 새로고침한다.
    // (recommend/no_change는 일정이 그대로이므로 불필요한 새로고침을 피한다)
    if (result.mode === "edit") {
      await loadItineraries();
    }

    return result;
  }

  // 여행 경로 조회
  async function fetchRoute(id) {
    return await getRoute(id);
  }

  return (
    <ItineraryContext.Provider
      value={{
        itineraries,
        loading,
        refresh: loadItineraries,
        create,
        update,
        patch,
        remove,
        regenerate,
        revise,
        fetchRoute,
      }}
    >
      {children}
    </ItineraryContext.Provider>
  );
}

export function useItineraries() {
  const ctx = useContext(ItineraryContext);

  if (!ctx) {
    throw new Error(
      "useItineraries must be used within ItineraryProvider"
    );
  }

  return ctx;
}
