import styles from './itinerary/itinerary.module.css'
import AppHeader from './itinerary/AppHeader.jsx'
import ChatPanel from './itinerary/ChatPanel.jsx'
import ItineraryEditor from './itinerary/ItineraryEditor.jsx'
import MapPanel from './itinerary/MapPanel.jsx'

export default function ItineraryPage() {
  return (
    <div className={styles.page}>
      <AppHeader />
      <div className={styles.stage}>
        <ChatPanel />
        <ItineraryEditor />
        <MapPanel />
      </div>
    </div>
  )
}
