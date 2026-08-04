import { useEffect, useRef, useState } from 'react'
import { createItinerary } from '../../api/itinerary'
import { useNavigate } from 'react-router-dom'
import styles from './chat.module.css'
import cx from '../../utils/cx.js'
import { STEPS } from './questionSteps.js'

const READY_DELAY_MS = 1800

let uid = 100
const nextId = () => ++uid

const COMPANION_TYPE_MAP = {
  가족: 'family',
  친구: 'friend',
  연인: 'couple',
  혼자: 'solo',
}

const TRANSPORT_MAP = {
  렌터카: 'car',
  버스: 'bus',
  자가용: 'car',
  택시: 'taxi',
}

const STYLE_MAP = {
  힐링: 'healing',
  힐링여행: 'healing',
  액티비티: 'activity',
  맛집: 'food',
  트레킹: 'trekking',
  가족여행: 'family',
}

const parseNights = (durationText) => {
  if (!durationText) return 1

  if (durationText.includes('당일')) {
    return 0
  }

  const match = durationText.match(/(\d+)\s*박/)

  if (match) {
    return Number.parseInt(match[1], 10)
  }

  return 1
}

const formatLocalDate = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')

  return `${year}-${month}-${day}`
}

const buildDateRange = (nights) => {
  const start = new Date()
  const end = new Date(start)

  end.setDate(end.getDate() + nights)

  return {
    start_date: formatLocalDate(start),
    end_date: formatLocalDate(end),
  }
}

const getCompanionCount = (companion) => {
  if (companion === '혼자') return 1
  if (companion === '가족') return 3
  if (companion === '친구') return 2
  if (companion === '연인') return 2

  return 1
}

export default function ChatColumn({
  answers,
  setAnswers,
  ready,
  onReady,
  setItineraryId,
  itineraryId,
}) {
  const [history, setHistory] = useState([
    {
      id: nextId(),
      type: 'msg',
      me: false,
      lines: [
        '안녕하세요! 😊',
        '원하시는 제주 여행을 알려주세요.',
      ],
    },
    {
      id: nextId(),
      type: 'question',
      stepIndex: 0,
    },
  ])

  const [stepIndex, setStepIndex] = useState(0)
  const [input, setInput] = useState('')

  const bodyRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!bodyRef.current) return

    requestAnimationFrame(() => {
      if (bodyRef.current) {
        bodyRef.current.scrollTop =
          bodyRef.current.scrollHeight
      }
    })
  }, [history, ready, stepIndex])

  const finishFlow = async (finalAnswers) => {
    try {
      const nights = parseNights(finalAnswers.duration)

      const { start_date, end_date } =
        buildDateRange(nights)

      const itinerary = await createItinerary({
        title: '제주 맞춤 여행',
        subtitle: `${finalAnswers.companion} 여행`,

        start_date,
        end_date,

        companion_type:
          COMPANION_TYPE_MAP[
            finalAnswers.companion
          ] ?? 'solo',

        companion_count: getCompanionCount(
          finalAnswers.companion
        ),

        transport:
          TRANSPORT_MAP[
            finalAnswers.transport
          ] ?? 'car',

        style:
          STYLE_MAP[finalAnswers.style] ??
          'healing',

        budget_per_person: 500000,

        accommodation_cost: 150000,
        transport_cost: 100000,
        activity_cost: 50000,
        food_cost: 100000,
        etc_cost: 50000,

        status: 'draft',
        is_public: false,
      })

      console.log('생성된 일정:', itinerary)

      setItineraryId(itinerary.id)

      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'msg',
          me: false,
          lines: [
            '완벽해요! 정보를 정리해서 멋진 일정을 만들어볼게요 🎉',
          ],
        },
        {
          id: nextId(),
          type: 'card',
          title: '✅ 입력된 조건 확인',
          rows: STEPS.map((step) => ({
            ic: step.icon,
            label: step.label,
            value: finalAnswers[step.key],
          })),
        },
      ])

      setTimeout(onReady, READY_DELAY_MS)
    } catch (error) {
      console.error('일정 생성 실패:', error)
    }
  }

  const answerStep = (key, value) => {
    if (!value.trim()) return

    setHistory((prev) => [
      ...prev,
      {
        id: nextId(),
        type: 'msg',
        me: true,
        lines: [value],
      },
    ])

    const nextAnswers = {
      ...answers,
      [key]: value,
    }

    setAnswers(nextAnswers)

    const next = stepIndex + 1
    setStepIndex(next)

    if (next < STEPS.length) {
      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'question',
          stepIndex: next,
        },
      ])
    } else {
      finishFlow(nextAnswers)
    }
  }

  const sendMsg = () => {
    const text = input.trim()

    if (!text) return

    setInput('')

    const currentStep = STEPS[stepIndex]

    if (
      currentStep &&
      currentStep.type === 'text'
    ) {
      answerStep(currentStep.key, text)
      return
    }

    setHistory((prev) => [
      ...prev,
      {
        id: nextId(),
        type: 'msg',
        me: true,
        lines: [text],
      },
    ])

    setTimeout(() => {
      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'msg',
          me: false,
          lines: [
            '알겠습니다! 반영해서 일정에 바로 적용할게요 🌿',
          ],
        },
      ])
    }, 700)
  }

  const flowDone =
    stepIndex >= STEPS.length

  return (
    <div className={styles.chatCol}>
      <div className={styles.chatHead}>
        <div className={styles.mark}>🗿</div>

        <div>
          <h2>AI 여행 코치</h2>
          <p>
            조건을 말해주시면 일정을 만들어드려요
          </p>
        </div>

        <div className={styles.status}>
          <span className={styles.pulse}></span>
          대화 중
        </div>
      </div>

      <div
        className={styles.chatBody}
        ref={bodyRef}
      >
        {history.map((item) => {
          if (item.type === 'card') {
            return (
              <div
                className={styles.chatCard}
                key={item.id}
              >
                <h5>{item.title}</h5>

                {item.rows.map((row) => (
                  <div
                    className={styles.ccRow}
                    key={row.label}
                  >
                    <div className={styles.ic}>
                      {row.ic}
                    </div>

                    <b>{row.value}</b>
                    <span>{row.label}</span>
                  </div>
                ))}
              </div>
            )
          }

          if (item.type === 'question') {
            const step =
              STEPS[item.stepIndex]

            const alreadyAnswered =
              item.stepIndex < stepIndex

            return (
              <div
                className={styles.msg}
                key={item.id}
              >
                <div className={styles.who}>
                  🌿
                </div>

                <div className={styles.bubble}>
                  {step.question}

                  {step.type === 'toggle' &&
                    !alreadyAnswered && (
                      <div
                        className={
                          styles.toggleRow
                        }
                      >
                        {step.options.map(
                          (option) => (
                            <button
                              key={option}
                              type="button"
                              className={
                                styles.toggleBtn
                              }
                              onClick={() =>
                                answerStep(
                                  step.key,
                                  option
                                )
                              }
                            >
                              {option}
                            </button>
                          )
                        )}
                      </div>
                    )}

                  {step.type === 'text' &&
                    !alreadyAnswered && (
                      <div
                        className={
                          styles.stepHint
                        }
                      >
                        아래 입력창에 직접
                        답해주세요 (
                        {step.placeholder})
                      </div>
                    )}
                </div>
              </div>
            )
          }

          return (
            <div
              className={cx(
                styles.msg,
                item.me && styles.me
              )}
              key={item.id}
            >
              <div className={styles.who}>
                {item.me ? '나' : '🌿'}
              </div>

              <div className={styles.bubble}>
                {item.lines.map(
                  (line, index) => (
                    <span key={index}>
                      {line}

                      {index <
                        item.lines.length -
                          1 && <br />}
                    </span>
                  )
                )}
              </div>
            </div>
          )
        })}

        {flowDone && (
          <div className={styles.msg}>
            <div className={styles.who}>
              🌿
            </div>

            {ready ? (
              <div className={styles.bubble}>
                일정이 완성됐어요! 확인하러
                가볼까요? 🎉
                <br />

                <span
                  className={styles.miniBtn}
                  onClick={() =>
                    navigate(
                      `/itinerary/${itineraryId}`
                    )
                  }
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
              !flowDone &&
              STEPS[stepIndex]?.type ===
                'text'
                ? STEPS[stepIndex]
                    .placeholder
                : '메시지를 입력하세요...'
            }
            value={input}
            onChange={(event) =>
              setInput(event.target.value)
            }
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                sendMsg()
              }
            }}
          />

          <button
            type="button"
            className={styles.sendBtn}
            onClick={sendMsg}
          >
            →
          </button>
        </div>
      </div>
    </div>
  )
}