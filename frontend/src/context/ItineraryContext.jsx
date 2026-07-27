import { createContext, useContext, useState } from 'react'

const ItineraryContext = createContext(null)

// 백엔드 GET /api/travel/itineraries/ 응답 형태와 필드명을 맞춘 목업.
// 실제로는 /itinerary 에서 편집한 일정이 저장되어 쌓이지만, 아직 API 연결 전이라
// "저장된 일정"을 미리 몇 개 채워둔 상태로 보여준다.
const SEED_ITINERARIES = [
  {
    id: 101,
    title: '제주 2박 3일 힐링 여행',
    subtitle: '부모님과 함께',
    startDate: '2026-07-25',
    endDate: '2026-07-27',
    durationLabel: '2박 3일',
    companionCount: 2,
    totalCost: 438700,
    status: 'draft',
    statusDisplay: '임시저장',
  },
  {
    id: 102,
    title: '제주 1박 2일 액티비티 여행',
    subtitle: '친구들과 함께',
    startDate: '2026-05-02',
    endDate: '2026-05-03',
    durationLabel: '1박 2일',
    companionCount: 4,
    totalCost: 256000,
    status: 'confirmed',
    statusDisplay: '확정',
  },
]

export function ItineraryProvider({ children }) {
  const [itineraries] = useState(SEED_ITINERARIES)
  return (
    <ItineraryContext.Provider value={{ itineraries }}>{children}</ItineraryContext.Provider>
  )
}

export function useItineraries() {
  const ctx = useContext(ItineraryContext)
  if (!ctx) throw new Error('useItineraries must be used within ItineraryProvider')
  return ctx
}
