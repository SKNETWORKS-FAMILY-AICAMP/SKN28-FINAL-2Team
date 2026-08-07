import { useState } from 'react'
import { useParams } from 'react-router-dom'
import styles from './itinerary/itinerary.module.css'
import AppHeader from './itinerary/AppHeader.jsx'
import ChatPanel from './itinerary/ChatPanel.jsx'
import ItineraryEditor from './itinerary/ItineraryEditor.jsx'
import MapPanel from './itinerary/MapPanel.jsx'

export default function ItineraryPage() {
  const { id } = useParams()

  const [activeDay, setActiveDay] = useState(1)

  const [refreshKey, setRefreshKey] = useState(0)

  const bumpRefreshKey = () => {
    setRefreshKey((prev) => prev + 1)
  }

  return (
    <div className={styles.page}>
      <AppHeader />

      <div className={styles.stage}>
        <ChatPanel onRevised={bumpRefreshKey} />

        <ItineraryEditor
          activeDay={activeDay}
          setActiveDay={setActiveDay}
          refreshKey={refreshKey}
          onChanged={bumpRefreshKey}
        />

        <MapPanel
          itineraryId={id}
          activeDay={activeDay}
          refreshKey={refreshKey}
        />
      </div>
    </div>
  )
}
