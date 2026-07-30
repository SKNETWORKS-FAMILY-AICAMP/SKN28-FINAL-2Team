import { useState } from 'react'
import styles from './chat/chat.module.css'
import AppHeader from './chat/AppHeader.jsx'
import ChatColumn from './chat/ChatColumn.jsx'
import SummaryColumn from './chat/SummaryColumn.jsx'
import { INITIAL_ANSWERS } from './chat/questionSteps.js'

export default function ChatPage() {
  const [answers, setAnswers] = useState(INITIAL_ANSWERS)
  const [ready, setReady] = useState(false)

  return (
    <div className={styles.page}>
      <AppHeader />
      <div className={styles.stage}>
        <ChatColumn
          answers={answers}
          setAnswers={setAnswers}
          ready={ready}
          onReady={() => setReady(true)}
        />
        <SummaryColumn answers={answers} ready={ready} />
      </div>
    </div>
  )
}
