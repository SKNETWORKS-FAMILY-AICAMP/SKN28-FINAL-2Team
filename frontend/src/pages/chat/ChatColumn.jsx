import { useEffect, useRef, useState } from 'react'
import { createItinerary } from "../../api/itinerary";
import { useNavigate } from 'react-router-dom'
import styles from './chat.module.css'
import cx from '../../utils/cx.js'
import { STEPS } from './questionSteps.js'

const READY_DELAY_MS = 1800

let uid = 100
const nextId = () => ++uid

export default function ChatColumn({ answers, setAnswers, ready, onReady, setItineraryId, itineraryId }) {
  const [history, setHistory] = useState([
    { id: nextId(), type: 'msg', me: false, lines: ['안녕하세요! 😊', '원하시는 제주 여행을 알려주세요.'] },
    { id: nextId(), type: 'question', stepIndex: 0 },
  ])
  const [stepIndex, setStepIndex] = useState(0)
  const [input, setInput] = useState('')
  const bodyRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (bodyRef.current) {
      // rAF로 한 프레임 뒤에 스크롤해서, 방금 렌더된(타이핑 표시·완료 메시지 등) 말풍선의
      // 실제 높이가 반영된 뒤 맨 아래로 이동하도록 함 → 마지막 버튼 클릭 시 내용이 화면 밖으로 밀려나지 않음
      requestAnimationFrame(() => {
        if (bodyRef.current) {
          bodyRef.current.scrollTop = bodyRef.current.scrollHeight
        }
      })
    }
  }, [history, ready, stepIndex])

  const finishFlow = async (finalAnswers) => {
    try {
      const itinerary = await createItinerary({

  title: "제주 맞춤 여행",
  subtitle: `${finalAnswers.companion} 여행`,

  start_date: "2026-08-01",
  end_date: "2026-08-03",

  companion_count:
    finalAnswers.companion === "가족"
      ? 3
      : finalAnswers.companion === "친구"
      ? 2
      : 2,

  style:
    finalAnswers.style === "힐링"
      ? "healing"
      : finalAnswers.style === "액티비티"
      ? "activity"
      : finalAnswers.style === "맛집"
      ? "food"
      : "family",

  budget_per_person: 500000,

  accommodation_cost:150000,
  transport_cost:100000,
  activity_cost:50000,
  food_cost:100000,
  etc_cost:50000,

  status:"draft",
  is_public:false
});

    console.log("생성된 일정:", itinerary);

    // 생성된 일정 id 저장
    setItineraryId(itinerary.id);


    setHistory((prev) => [
      ...prev,

      {
        id: nextId(),
        type: 'msg',
        me:false,
        lines:[
          '완벽해요! 정보를 정리해서 멋진 일정을 만들어볼게요 🎉'
        ]
      },

      {
        id: nextId(),
        type:'card',
        title:'✅ 입력된 조건 확인',
        rows: STEPS.map((s)=>({
          ic:s.icon,
          label:s.label,
          value:finalAnswers[s.key]
        }))
      }
    ]);


    setTimeout(onReady, READY_DELAY_MS);


  } catch(error){

    console.error(
      "일정 생성 실패:",
      error
    );

  }
};

  const answerStep = (key, value) => {
    if (!value.trim()) return

    setHistory((prev) => [...prev, { id: nextId(), type: 'msg', me: true, lines: [value] }])

    const nextAnswers = { ...answers, [key]: value }
    setAnswers(nextAnswers)

    const next = stepIndex + 1
    setStepIndex(next)

    if (next < STEPS.length) {
      setHistory((prev) => [...prev, { id: nextId(), type: 'question', stepIndex: next }])
    } else {
      finishFlow(nextAnswers)
    }
  }

  const sendMsg = () => {
    const text = input.trim()
    if (!text) return
    setInput('')

    const currentStep = STEPS[stepIndex]
    if (currentStep && currentStep.type === 'text') {
      answerStep(currentStep.key, text)
      return
    }

    // 가이드 질문 흐름과 무관한 자유 대화(예: 완료 후 추가 요청)는 일반 응답으로 처리
    setHistory((prev) => [...prev, { id: nextId(), type: 'msg', me: true, lines: [text] }])
    setTimeout(() => {
      setHistory((prev) => [
        ...prev,
        { id: nextId(), type: 'msg', me: false, lines: ['알겠습니다! 반영해서 일정에 바로 적용할게요 🌿'] },
      ])
    }, 700)
  }

  const flowDone = stepIndex >= STEPS.length

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
        {history.map((item) => {
          if (item.type === 'card') {
            return (
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
            )
          }

          if (item.type === 'question') {
            const step = STEPS[item.stepIndex]
            const alreadyAnswered = item.stepIndex < stepIndex
            return (
              <div className={styles.msg} key={item.id}>
                <div className={styles.who}>🌿</div>
                <div className={styles.bubble}>
                  {step.question}
                  {step.type === 'toggle' && !alreadyAnswered && (
                    <div className={styles.toggleRow}>
                      {step.options.map((opt) => (
                        <button
                          key={opt}
                          className={styles.toggleBtn}
                          onClick={() => answerStep(step.key, opt)}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  )}
                  {step.type === 'text' && !alreadyAnswered && (
                    <div className={styles.stepHint}>아래 입력창에 직접 답해주세요 (예: {step.placeholder})</div>
                  )}
                </div>
              </div>
            )
          }

          return (
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
        })}

        {/* 4개 질문에 모두 답하면, typing 표시 → 완료 메시지로 전환 */}
        {flowDone && (
          <div className={styles.msg}>
            <div className={styles.who}>🌿</div>
            {ready ? (
              <div className={styles.bubble}>
                일정이 완성됐어요! 확인하러 가볼까요? 🎉
                <br />
                <span
                  className={styles.miniBtn}
                  onClick={() => navigate(`/itinerary/${itineraryId}`)}
                >
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
        )}
      </div>

      <div className={styles.chatFoot}>
        <div className={styles.inputBar}>
          <input
            type="text"
            placeholder={
              !flowDone && STEPS[stepIndex]?.type === 'text'
                ? STEPS[stepIndex].placeholder
                : '메시지를 입력하세요...'
            }
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
