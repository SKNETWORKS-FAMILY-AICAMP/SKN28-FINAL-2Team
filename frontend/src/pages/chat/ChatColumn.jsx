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

const normalizeDuration = (text) => {
  const value = text.trim().replace(/\s+/g, '');

  if (value === '당일' || value === '당일치기') {
    return '당일';
  }

  const nightOnlyMatch = value.match(/^(\d+)박$/);

  if (nightOnlyMatch) {
    const nights = Number(nightOnlyMatch[1]);

    if (nights < 1) return null;

    return `${nights}박 ${nights + 1}일`;
  }

  const nightDayMatch = value.match(/^(\d+)박(\d+)일$/);

  if (!nightDayMatch) return null;

  const nights = Number(nightDayMatch[1]);
  const days = Number(nightDayMatch[2]);

  if (nights < 1 || days !== nights + 1) return null;

  return `${nights}박 ${days}일`;
};

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
const calculateTripDuration = (startDate, endDate) => {
  if (!startDate || !endDate) return null;

  const start = new Date(startDate);
  const end = new Date(endDate);

  const diffTime = end.getTime() - start.getTime();
  const nights = Math.round(diffTime / (1000 * 60 * 60 * 24));

  if (nights < 0) return null;

  if (nights === 0) {
    return {
      label: "당일",
      nights: 0,
      days: 1,
    };
  }

  return {
    label: `${nights}박 ${nights + 1}일`,
    nights,
    days: nights + 1,
  };
};

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
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

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
          value:
            step.key === 'travelDates'
              ? finalAnswers.travelDates?.duration
              : finalAnswers[step.key],
        })),
      },
    ])

    try {
      const {
        startDate,
        endDate,
      } = finalAnswers.travelDates

      const itinerary = await createItinerary({
        title: '제주 맞춤 여행',
        subtitle: `${finalAnswers.companion} 여행`,

        start_date: startDate,
        end_date: endDate,

        companion_type:
          COMPANION_TYPE_MAP[
            finalAnswers.companion
          ] ?? 'solo',

        companion_count: getCompanionCount(
          finalAnswers.companion
        ),

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

      const initialMessages = [
        {
          id: crypto.randomUUID(),
          me: false,
          text: ['✅ 입력한 여행 조건입니다.',
            '',
            `👥 동행자: ${finalAnswers.companion}`,
            `📅 기간: ${finalAnswers.travelDates.duration}`,
            `🍃 여행 스타일: ${finalAnswers.style}`,
          ].join('\n'),
        },
        {
          id: crypto.randomUUID(),
          me: false,
          text: '짜잔! 고민없이 제주 여행 일정을 완성했어요 🎉',
          mini: '일정 확인하기 →',
        },
      ]

      sessionStorage.setItem(
        `itinerary-chat-${itinerary.id}`,
        JSON.stringify(initialMessages),
      )
      setTimeout(onReady, READY_DELAY_MS)
    } catch (error) {
      console.error('일정 생성 실패:', error)
      
      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'msg',
          me: false,
          lines: [
            '일정을 생성하지 못했어요. 잠시 후 다시 시도해주세요.',
          ],
        },
      ])
    }
  }

    const answerStep = (key, value) => {
      if (!value.trim()) return
    
      let finalValue = value.trim();

      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'msg',
          me: true,
          lines: [finalValue],
        },
      ])

      if (key === 'duration') {
        const normalized = normalizeDuration(finalValue);

        if (!normalized) {
          setHistory((prev) => [
            ...prev,
            {
              id: nextId(),
              type: 'msg',
              me: false,
              lines: [
                '여행 기간 형식이 올바르지 않아요.',
                '(예: 당일, 1박 2일, 2박 3일)',
              ],
            },
          ]);

          return;
        }

        finalValue = normalized;
      }


    const nextAnswers = {
      ...answers,
      [key]: finalValue,
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
      currentStep.type === 'dateRange'
    ) {
      return
    }

    if (
      currentStep &&
      currentStep.type === 'toggle'
    ) {
      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'msg',
          me: false,
          lines: ['버튼을 눌러 선택해주세요.'],
        },
      ])

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

                  {step.type === 'dateRange' &&
                    !alreadyAnswered && (
                      <div className={styles.dateRange}>
                        <div className={styles.dateInputs}>
                          <label className={styles.dateField}>
                            <span>출발일</span>

                            <input
                              type="date"
                              value={startDate}
                              min={new Date().toISOString().split('T')[0]}
                              onChange={(event) => {
                                const value = event.target.value

                                setStartDate(value)

                                if (endDate && value > endDate) {
                                  setEndDate('')
                                }
                              }}
                            />
                          </label>

                          <label className={styles.dateField}>
                            <span>도착일</span>

                            <input
                              type="date"
                              value={endDate}
                              min={
                                startDate ||
                                new Date().toISOString().split('T')[0]
                              }
                              onChange={(event) =>
                                setEndDate(event.target.value)
                              }
                            />
                          </label>
                        </div>

                        {startDate && endDate && (
                          <div className={styles.dateSummary}>
                            <div className={styles.dateText}>
                              {startDate} ~ {endDate}
                            </div>
                            
                            <strong>
                              {calculateTripDuration(startDate, endDate)?.label}
                            </strong>
                          </div>
                        )}

                        <button
                          type="button"
                          className={styles.dateCompleteBtn}
                          disabled={!startDate || !endDate}
                          onClick={() => {
                            const duration = calculateTripDuration(startDate, endDate)

                            if (!duration) return

                            const value = {
                              startDate,
                              endDate,
                              duration: duration.label,
                            }

                            setHistory((prev) => [
                              ...prev,
                              {
                                id: nextId(),
                                type: 'msg',
                                me: true,
                                lines: [
                                  duration.label,
                                ],
                              },
                            ])

                            const nextAnswers = {
                              ...answers,
                              travelDates: value,
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
                          }}
                        >
                          날짜 선택 완료
                        </button>
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
            disabled={
              !flowDone &&
              (
                STEPS[stepIndex]?.type === 'toggle' ||
                STEPS[stepIndex]?.type === 'dateRange'
              )
            }
            placeholder={
              !flowDone && STEPS[stepIndex]?.type === 'toggle'
                ? '위 버튼을 눌러 선택해주세요'
                : !flowDone && STEPS[stepIndex]?.type === 'dateRange'
                  ? '위 달력에서 날짜를 선택해주세요'
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
            disabled={
              !flowDone &&
              (
                STEPS[stepIndex]?.type === 'toggle' ||
                STEPS[stepIndex]?.type === 'dateRange'
              )
            }
          >
            →
          </button>
        </div>
      </div>
    </div>
  )
}