import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import styles from './chat.module.css'
import cx from '../../utils/cx.js'

const INITIAL_HISTORY = [
  { id: 1, type: 'msg', me: false, lines: ['안녕하세요! 😊', '원하시는 제주 여행을 알려주세요.'] },
  { id: 2, type: 'msg', me: true, lines: ['부모님과 2박 3일 힐링 여행을 계획하고 싶어요.'] },
  { id: 3, type: 'msg', me: false, lines: ['좋아요! 몇 가지 더 여쭤볼게요 😊', '예산은 어느 정도로 생각하시나요?'] },
  { id: 4, type: 'msg', me: true, lines: ['1인당 50만원 정도 생각하고 있어요.'] },
  { id: 5, type: 'msg', me: false, lines: ['알겠습니다! 여행 스타일도 알려주세요.'] },
  { id: 6, type: 'msg', me: true, lines: ['조용하고 여유로운 힐링 위주로요.'] },
  { id: 7, type: 'msg', me: false, lines: ['완벽해요! 정보를 정리해서 멋진 일정을 만들어볼게요 🎉'] },
  {
    id: 8,
    type: 'card',
    title: '✅ 입력된 조건 확인',
    rows: [
      { ic: '👥', label: '인원', value: '부모님 (2명)' },
      { ic: '📅', label: '기간', value: '2박 3일' },
      { ic: '🍃', label: '스타일', value: '힐링 / 여유로운 여행' },
      { ic: '💰', label: '예산', value: '1인당 50만원' },
    ],
  },
]

const CHIPS = [
  { text: '예산을 조금 낮추고 싶어요', label: '예산 낮추기' },
  { text: '맛집도 일정에 넣어주세요', label: '맛집 알아보기' },
  { text: '액티비티도 추가해주세요', label: '액티비티 추가' },
]

const READY_DELAY_MS = 3200

export default function ChatColumn({ ready, onReady }) {
  const [history, setHistory] = useState(INITIAL_HISTORY)
  const [input, setInput] = useState('')
  const bodyRef = useRef(null)

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [history, ready])

  useEffect(() => {
    const t = setTimeout(onReady, READY_DELAY_MS)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const navigate = useNavigate()

  const sendMsg = () => {
    const text = input.trim()
    if (!text) return

    setHistory((prev) => [...prev, { id: Date.now(), type: 'msg', me: true, lines: [text] }])
    setInput('')

    setTimeout(() => {
      setHistory((prev) => [
        ...prev,
        { id: Date.now() + 1, type: 'msg', me: false, lines: ['알겠습니다! 반영해서 일정에 바로 적용할게요 🌿'] },
      ])
    }, 700)
  }

  return (
    <div className={styles.chatCol}>
      <div className={styles.chatHead}>
        <div className={styles.mark}>🗿</div>
        <div>
          <h2>AI 여행 코치</h2>
          <p>조건을 말해주시면 일정을 만들어드려요</p>
        </div>
        <div className={styles.status}>
          <span className={styles.pulse}></span>대화 중
        </div>
      </div>

      <div className={styles.chatBody} ref={bodyRef}>
        {history.map((item) =>
          item.type === 'card' ? (
            <div className={styles.chatCard} key={item.id}>
              <h5>{item.title}</h5>
              {item.rows.map((row) => (
                <div className={styles.ccRow} key={row.label}>
                  <div className={styles.ic}>{row.ic}</div>
                  <b>{row.value}</b>
                  <span>{row.label}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className={cx(styles.msg, item.me && styles.me)} key={item.id}>
              <div className={styles.who}>{item.me ? '나' : '🌿'}</div>
              <div className={styles.bubble}>
                {item.lines.map((line, i) => (
                  <span key={i}>
                    {line}
                    {i < item.lines.length - 1 && <br />}
                  </span>
                ))}
              </div>
            </div>
          )
        )}

        {/* trailing indicator: typing dots until the itinerary is "ready" */}
        <div className={styles.msg}>
          <div className={styles.who}>🌿</div>
          {ready ? (
            <div className={styles.bubble}>
              일정이 완성됐어요! 확인하러 가볼까요? 🎉
              <br />
              <span className={styles.miniBtn} onClick={() => navigate('/itinerary')}>
                일정 확인하기 →
              </span>
            </div>
          ) : (
            <div className={styles.bubble}>
              <div className={styles.typing}>
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className={styles.chatFoot}>
        <div className={styles.chips}>
          {CHIPS.map((c) => (
            <button key={c.text} className={styles.chip} onClick={() => setInput(c.text)}>
              {c.label}
            </button>
          ))}
        </div>
        <div className={styles.inputBar}>
          <input
            type="text"
            placeholder="메시지를 입력하세요..."
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
