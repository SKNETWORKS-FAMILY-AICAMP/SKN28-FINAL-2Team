import { useState } from 'react'
import styles from './itinerary/itinerary.module.css'
import AppHeader from './itinerary/AppHeader.jsx'
import ChatPanel from './itinerary/ChatPanel.jsx'
import ItineraryEditor from './itinerary/ItineraryEditor.jsx'
import MapPanel from './itinerary/MapPanel.jsx'

export default function ItineraryPage() {
  // 채팅으로 일정을 수정(revise)한 뒤, 가운데 일정 패널(ItineraryEditor)이
  // 이 값을 감지해 최신 데이터를 다시 불러오도록 하는 트리거.
  const [refreshKey, setRefreshKey] = useState(0)
  const bumpRefreshKey = () => setRefreshKey((k) => k + 1)

  return (
    <div className={styles.page}>
      <AppHeader />
      <div className={styles.stage}>
        <ChatPanel onRevised={bumpRefreshKey} />
        <ItineraryEditor refreshKey={refreshKey} />
        <MapPanel />
      </div>
    </div>
  )
}
