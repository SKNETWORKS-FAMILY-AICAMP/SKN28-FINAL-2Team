import { useEffect, useRef, useState } from 'react'
import styles from './itinerary.module.css'
import cx from '../../utils/cx.js'

const INITIAL_MESSAGES = [
  {
    id: 1,
    me: false,
    text: '짜잔! 고민없이 제주 2박 3일 힐링 여행 일정을 완성했어요 🎉',
    mini: '일정 확인하기 →',
  },
  { id: 2, me: true, text: '우도 대신 협재해변으로 바꿔주세요.' },
  { id: 3, me: false, text: '알겠습니다! 우도를 협재해변으로 바꿨어요. 이동 시간도 20분 줄었어요.' },
  { id: 4, me: true, text: '자녀에 흑돼지 맛집 추천해줘.' },
  { id: 5, me: false, text: '네! 오른쪽 일정에 흑돼지 맛집을 추가했어요 🐷' },
]

const CHIPS = ['숙소도 추천해주세요', '근처 맛집도 알려주세요', '액티비티도 넣어주세요']
const CHIP_LABELS = ['숙소 추가', '맛집 추가', '액티비티 추가']

export default function ChatPanel() {
  const [messages, setMessages] = useState(INITIAL_MESSAGES)
  const [input, setInput] = useState('')
  const bodyRef = useRef(null)

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [messages])

  const sendMsg = () => {
    const text = input.trim()
    if (!text) return

    setMessages((prev) => [...prev, { id: Date.now(), me: true, text }])
    setInput('')

    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, me: false, text: '알겠습니다! 일정에 바로 반영할게요 🌿' },
      ])
    }, 700)
  }

  return (
    <div className={styles.chatCol}>
      <div className={styles.chatHead}>
        <div className={styles.mark}>🗿</div>
        <div>
          <h2>AI 여행 코치</h2>
          <p>대화로 바로 수정해보세요</p>
        </div>
      </div>

      <div className={styles.chatBody} ref={bodyRef}>
        {messages.map((m) => (
          <div key={m.id} className={cx(styles.msg, m.me && styles.me)}>
            <div className={styles.who}>{m.me ? '나' : '🌿'}</div>
            <div className={styles.bubble}>
              {m.text}
              {m.mini && (
                <>
                  <br />
                  <span className={styles.miniBtn}>{m.mini}</span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.chatFoot}>
        <div className={styles.chips}>
          {CHIPS.map((text, i) => (
            <button key={text} className={styles.chip} onClick={() => setInput(text)}>
              {CHIP_LABELS[i]}
            </button>
          ))}
        </div>
        <div className={styles.inputBar}>
          <input
            type="text"
            placeholder="예시를 입력하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') sendMsg()
            }}
          />
          <button className={styles.sendBtn} onClick={sendMsg}>
            →
          </button>
        </div>
      </div>
    </div>
  )
}
