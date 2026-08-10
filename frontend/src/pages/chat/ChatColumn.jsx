import { useEffect, useRef, useState } from 'react'
import { createItinerary } from '../../api/itinerary'
import { useNavigate } from 'react-router-dom'
import styles from './chat.module.css'
import cx from '../../utils/cx.js'
import { STEPS } from './questionSteps.js'


const READY_DELAY_MS = 1800
const CHAT_COLUMN_STORAGE_KEY = "travel-chat-column";

let uid = 100
const nextId = () => ++uid

const COMPANION_TYPE_MAP = {
  가족: 'family',
  친구: 'friend',
  연인: 'couple',
  혼자: 'solo',
}

// 나이대 토글 옵션("20대" 등)을 백엔드 age_group 필드가 기대하는
// 숫자 문자열("20")로 변환한다. services.py가 f"{age_group}대" 형태로
// 다시 조합해서 LLM/AIHub 조회에 사용하기 때문에 접미사 없이 숫자만 저장한다.
const AGE_GROUP_MAP = {
  '10대': '10',
  '20대': '20',
  '30대': '30',
  '40대': '40',
  '50대': '50',
  '60대 이상': '60',
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
  const getSavedChatColumn = () => {
    try {
      const saved = sessionStorage.getItem(CHAT_COLUMN_STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch (error) {
      console.error("채팅 복원 실패:", error);
      return null;
    }
  };

  const savedChatColumn = getSavedChatColumn();

  const [history, setHistory] = useState(() => {
    if (Array.isArray(savedChatColumn?.history)) {
      return savedChatColumn.history;
    }

    return [
      {
        id: nextId(),
        type: "msg",
        me: false,
        lines: [
          "안녕하세요! 😊",
          "원하시는 제주 여행을 알려주세요.",
        ],
      },
      {
        id: nextId(),
        type: "question",
        stepIndex: 0,
      },
    ];
  });

  const [stepIndex, setStepIndex] = useState(
    savedChatColumn?.stepIndex ?? 0
  );

  const [input, setInput] = useState("");
  const [extraRequests, setExtraRequests] = useState(
    savedChatColumn?.extraRequests ?? []
  )
  const [isCreating, setIsCreating] = useState(false)

  const [startDate, setStartDate] = useState(
    savedChatColumn?.startDate ?? ""
  );

  const [endDate, setEndDate] = useState(
    savedChatColumn?.endDate ?? ""
  );

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

  useEffect(() => {
    try {
      sessionStorage.setItem(
        CHAT_COLUMN_STORAGE_KEY,
        JSON.stringify({
          history,
          stepIndex,
          startDate,
          endDate,
          extraRequests,
        })
      );
    } catch (error) {
      console.error("채팅 저장 실패:", error);
    }
  }, [history, stepIndex, startDate, endDate, extraRequests]);


  const finishFlow = async (finalAnswers) => {
    if (isCreating) return

    setIsCreating(true)

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
              ? finalAnswers.travelDates?.duration === '당일'
                ? [
                    `${finalAnswers.travelDates?.startDate.replaceAll('-', '.')} · 당일`,
                  ]
                : [
                    `${finalAnswers.travelDates?.startDate} ~ ${finalAnswers.travelDates?.endDate}`,
                    finalAnswers.travelDates?.duration,
                  ]
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
        age_group:
          AGE_GROUP_MAP[finalAnswers.ageGroup] ?? '',
        // 여행 스타일은 미리 정해둔 카테고리로 필터링하지 않고,
        // 사용자가 입력한 자유 텍스트 그대로 백엔드로 전달한다.
        // 백엔드는 이 텍스트를 그대로 RAG 검색 조건으로 사용해
        // 관광지 후보를 찾는다.
        style: finalAnswers.style ?? '',
        status: 'draft',
        is_public: false,
      })

      console.log('생성된 일정:', itinerary)

      setItineraryId(itinerary.id)

      const freeChatStartIndex = history.findIndex(
        (item) =>
          item.type === 'msg' &&
          item.me === false &&
          item.lines?.includes('기본 조건을 모두 확인했어요.')
      )

      const freeChatHistory =
        freeChatStartIndex >= 0
          ? history.slice(freeChatStartIndex + 1)
          : []

      const convertedHistory = freeChatHistory
        .filter((item) => item.type === 'msg')
        .map((item) => ({
          id: crypto.randomUUID(),
          me: item.me,
          text: item.lines.join('\n'),
        }))

      const dateLines =
        finalAnswers.travelDates.duration === '당일'
          ? [
              `📅 기간: ${finalAnswers.travelDates.startDate.replaceAll('-', '.')} · 당일`,
            ]
          : [
              `📅 기간: ${finalAnswers.travelDates.startDate} ~ ${finalAnswers.travelDates.endDate}`,
              `          ${finalAnswers.travelDates.duration}`,
            ]  

      const initialMessages = [
        {
          id: crypto.randomUUID(),
          me: false,
          text: [
            '✅ 입력한 여행 조건입니다.',
            '',
            `👥 동행자: ${finalAnswers.companion}`,
            ...dateLines,
            `🍃 여행 스타일: ${finalAnswers.style}`,
          ].join('\n'),
        },
        ...convertedHistory,
      ]

      sessionStorage.setItem(
        `itinerary-chat-${itinerary.id}`,
        JSON.stringify(initialMessages),
      )
      setTimeout(onReady, READY_DELAY_MS)
    } catch (error) {
      console.error('일정 생성 실패:', error)

      setIsCreating(false)
      
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
      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'msg',
          me: false,
          lines: [
            '기본 조건을 모두 확인했어요.',
            '추가하거나 빼고 싶은 장소, 음식, 제약사항을 자유롭게 입력해주세요.',
          ],
        },
      ])
    }
  }

    const sendMsg = () => {
      const text = input.trim()

      if (!text) return

      setInput('')

      const currentStep = STEPS[stepIndex]

      // 날짜 선택 단계에서는 입력창 사용 안 함
      if (
        currentStep &&
        currentStep.type === 'dateRange'
      ) {
        return
      }

      // 선택형 질문은 버튼으로만 답변
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

      // text 타입 질문 답변
      if (currentStep) {
        answerStep(currentStep.key, text)
      }
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

                    <b
                      className={
                        Array.isArray(row.value)
                          ? styles.dateValue
                          : undefined
                      }
                    >
                      {Array.isArray(row.value)
                        ? row.value.map((line, index) => (
                            <span key={index}>{line}</span>
                          ))
                        : row.value}
                    </b>
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
                  🍊
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
                                lines:
                                  duration.nights === 0
                                    ? [
                                        `${startDate.replaceAll('-', '.')} · 당일`,
                                      ]
                                    : [
                                        `${startDate} ~ ${endDate}`,
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
                              setHistory((prev) => [
                                ...prev,
                                {
                                  id: nextId(),
                                  type: 'msg',
                                  me: false,
                                  lines: [
                                    '기본 조건을 모두 확인했어요.',
                                    '추가하거나 빼고 싶은 장소, 음식, 제약사항을 자유롭게 입력해주세요.',
                                  ],
                                },
                              ])
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
                {item.me ? '나' : '🍊'}
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
            <div className={styles.who}>🍊</div>

            {ready ? (
              <div className={styles.bubble}>
                일정이 완성됐어요! 확인하러 가볼까요? 🎉
                <br />

                <span
                  className={styles.miniBtn}
                  onClick={() =>
                    navigate(`/itinerary/${itineraryId}`)
                  }
                >
                  일정 확인하기 →
                </span>
              </div>
            ) : isCreating ? (
              <div className={styles.bubble}>
                일정을 생성하고 있어요.

                <div className={styles.typing}>
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            ) : (
              <div className={styles.bubble}>
                추가 요청을 모두 입력하셨다면
                <br />
                아래 버튼을 눌러주세요.
                <br />

                <button
                  type="button"
                  className={styles.miniBtn}
                  onClick={() => finishFlow(answers)}
                >
                  이 조건으로 일정 생성하기 →
                </button>
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
};