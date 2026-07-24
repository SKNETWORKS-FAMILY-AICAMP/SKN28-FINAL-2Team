import { useState } from 'react'
import styles from './chat/chat.module.css'
import AppHeader from './chat/AppHeader.jsx'
import ChatColumn from './chat/ChatColumn.jsx'
import SummaryColumn from './chat/SummaryColumn.jsx'

export default function ChatPage() {
  const [ready, setReady] = useState(false)

  return (
    <div className={styles.page}>
      <AppHeader />
      <div className={styles.stage}>
        <ChatColumn ready={ready} onReady={() => setReady(true)} />
        <SummaryColumn ready={ready} />
      </div>
    </div>
  )
}
