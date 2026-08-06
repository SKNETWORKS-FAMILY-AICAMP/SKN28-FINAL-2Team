import { useEffect, useState } from 'react'
import styles from './chat/chat.module.css'
import AppHeader from './chat/AppHeader.jsx'
import ChatColumn from './chat/ChatColumn.jsx'
import SummaryColumn from './chat/SummaryColumn.jsx'
import { INITIAL_ANSWERS } from './chat/questionSteps.js'

const CHAT_PAGE_STORAGE_KEY = "travel-chat-page";

export default function ChatPage() {
  const [answers, setAnswers] = useState(() => {
  try {
    const saved = sessionStorage.getItem(CHAT_PAGE_STORAGE_KEY);

    return saved
      ? JSON.parse(saved).answers ?? INITIAL_ANSWERS
      : INITIAL_ANSWERS;
  } catch (error) {
    console.error("채팅 조건 복원 실패:", error);
    return INITIAL_ANSWERS;
  }
});

const [ready, setReady] = useState(() => {
  try {
    const saved = sessionStorage.getItem(CHAT_PAGE_STORAGE_KEY);

    return saved
      ? JSON.parse(saved).ready ?? false
      : false;
  } catch {
    return false;
  }
});

const [itineraryId, setItineraryId] = useState(() => {
  try {
    const saved = sessionStorage.getItem(CHAT_PAGE_STORAGE_KEY);

    return saved
      ? JSON.parse(saved).itineraryId ?? null
      : null;
  } catch {
    return null;
  }
});

useEffect(() => {
  try {
    sessionStorage.setItem(
      CHAT_PAGE_STORAGE_KEY,
      JSON.stringify({
        answers,
        ready,
        itineraryId,
      })
    );
  } catch (error) {
    console.error("채팅 조건 저장 실패:", error);
  }
}, [answers, ready, itineraryId]);

  return (
    <div className={styles.page}>
      <AppHeader />
      <div className={styles.stage}>
        <ChatColumn
          answers={answers}
          setAnswers={setAnswers}
          ready={ready}
          onReady={() => setReady(true)}
          setItineraryId={setItineraryId}
          itineraryId={itineraryId}
        />
        <SummaryColumn answers={answers} ready={ready} itineraryId={itineraryId} />
      </div>
    </div>
  )
}
