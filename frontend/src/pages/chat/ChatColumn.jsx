import { useEffect, useRef, useState } from 'react'
import { createItinerary, reviseItinerary } from '../../api/itinerary'
import styles from './chat.module.css'
import cx from '../../utils/cx.js'
import { STEPS } from './questionSteps.js'
import ItineraryPreview from "./ItineraryPreview.jsx"
import { useNavigate } from "react-router-dom"


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

const getItemTypeLabel = (item) => {
  if (item.restaurant) return '식당'
  if (item.accommodation) return '숙소'
  if (item.item_type === 'restaurant') return '식당'
  if (item.item_type === 'accommodation') return '숙소'
  return '관광지'
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
  const navigate = useNavigate()
  const [history, setHistory] = useState(() => {
    if (Array.isArray(savedChatColumn?.history)) {
      return savedChatColumn.history;
    }

    return [
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

  const [input, setInput] = useState("")
  const [isCreating, setIsCreating] = useState(false)
  const [isRevising, setIsRevising] = useState(false)
  const [openPreviewId, setOpenPreviewId] = useState(null)
  const [startDate, setStartDate] = useState(
    savedChatColumn?.startDate ?? ""
  );

  const [endDate, setEndDate] = useState(
    savedChatColumn?.endDate ?? ""
  );

  const bodyRef = useRef(null)

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
        })
      );
    } catch (error) {
      console.error("채팅 저장 실패:", error);
    }
  }, [history, stepIndex, startDate, endDate]);


  const finishFlow = async (finalAnswers) => {
    if (isCreating) return

    setIsCreating(true)

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

      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'itinerary',
          itinerary,
        },
      ])

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
      ]

      sessionStorage.setItem(
        `itinerary-chat-${itinerary.id}`,
        JSON.stringify(initialMessages),
      )
      setIsCreating(false)
      onReady()
      
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

    const sendMsg = async () => {
      const text = input.trim()

      if (!text) return

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

      if (
        currentStep &&
        currentStep.type === 'text'
      ) {
        answerStep(currentStep.key, text)
        setInput('')
        return
      }

      setInput('')

      setHistory((prev) => [
        ...prev,
        {
          id: nextId(),
          type: 'msg',
          me: true,
          lines: [text],
        },
      ])

      if (!itineraryId) {
        setHistory((prev) => [
          ...prev,
          {
            id: nextId(),
            type: 'msg',
            me: false,
            lines: ['수정할 일정이 아직 없어요.'],
          },
        ])

        return
      }

      try {
        setIsRevising(true)

        const updatedItinerary = await reviseItinerary(
          itineraryId,
          text
        )

        setHistory((prev) => [
          ...prev,
          {
            id: nextId(),
            type: 'msg',
            me: false,
            lines: [
              '요청하신 내용을 일정에 반영했어요. 🍊',
            ],
          },
          {
            id: nextId(),
            type: 'itinerary',
            itinerary: updatedItinerary,
          },
        ])

        setOpenPreviewId(null)
      } catch (error) {
        console.error('일정 수정 실패:', error)

        setHistory((prev) => [
          ...prev,
          {
            id: nextId(),
            type: 'msg',
            me: false,
            lines: [
              '일정을 수정하지 못했어요. 잠시 후 다시 시도해주세요.',
            ],
          },
        ])
      } finally {
        setIsRevising(false)
      }
    }

  const flowDone =
    stepIndex >= STEPS.length
  const currentStep = STEPS[stepIndex]

  const latestItineraryItem = [...history]
    .reverse()
    .find((item) => item.type === 'itinerary')

  const latestItineraryHistoryId = latestItineraryItem?.id

  const isInputDisabled =
    !flowDone &&
    (currentStep?.type === 'toggle' ||
    currentStep?.type === 'dateRange')

  return (
    <div className={styles.chatCol}>
      <div className={styles.chatHead}>
        <div className={styles.status}>
          <span className={styles.pulse}></span>
          대화 중
        </div>
      </div>

      <div
        className={styles.chatBody}
        ref={bodyRef}
      >
        <div className={styles.chatIntro}>
          <div className={styles.introMascot}>🗿</div>

          <h2>안녕하세요! 탐나플랜 AI예요 👋</h2>

          <p>여행을 시작하기 전에 알려주세요.</p>

        </div>
        {history.map((item) => {
          if (item.type === 'itinerary') {
            const isLatest = item.id === latestItineraryHistoryId
            const isPreviewOpen = openPreviewId === item.id
            return (
              <div key={item.id}>
                {/* 기존 텍스트 일정 */}
                <div className={styles.itineraryResult}>
                  {item.itinerary.days.map((day) => (
                    <div
                      key={day.dayNumber}
                      className={styles.itineraryDay}
                    >
                      <h2>{day.dayNumber}일차</h2>

                      {day.items.map((place, index) => (
                        <div
                          key={`${day.dayNumber}-${index}`}
                          className={styles.itineraryItem}
                        >
                          <strong>
                            [{getItemTypeLabel(place)}] {place.title}
                          </strong>

                          {place.description && (
                            <p>{place.description}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>

                {/* AI 안내 멘트 */}
                <div className={styles.previewMessageRow}>
                  <div className={styles.previewAvatar}>🍊</div>

                  <div className={styles.previewMessageBubble}>
                    <p>
                      제안해 드린 일정은 어떠셨나요?
                      <br />
                      일정은 취향에 맞게 자유롭게 변경할 수 있습니다.
                    </p>

                    <p>
                      복잡한 여행 일정을 한눈에 보기 쉽게 정리했어요!
                      <br />
                      [일정 미리보기] 버튼을 눌러 확인해 보세요.
                    </p>
                  </div>
                </div>

                {/* 말풍선 밖에 있는 미리보기 버튼 */}
                <button
                  type="button"
                  className={styles.previewBtn}
                  onClick={() =>
                    setOpenPreviewId(
                      isPreviewOpen ? null : item.id
                    )
                  }
                >
                  일정 미리보기
                </button>

                {isPreviewOpen && (
                  <div className={styles.previewArea}>
                    <ItineraryPreview itinerary={item.itinerary} />
                  </div>
                )}

                {isLatest && (
                  <button
                    type="button"
                    className={styles.confirmItineraryBtn}
                    onClick={() =>
                      navigate(`/review/${item.itinerary.id}`)
                    }
                  >
                    이 일정으로 확정하기 →
                  </button>
                )}
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

        {flowDone && isCreating && !ready && !latestItineraryItem && (
          <div className={styles.msg}>
            <div className={styles.who}>🍊</div>

            <div className={styles.bubble}>
              입력한 조건으로 일정 생성 중

              <div className={styles.typing}>
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        {flowDone && isRevising && (
          <div className={styles.msg}>
            <div className={styles.who}>🍊</div>

            <div className={styles.bubble}>
              요청하신 내용으로 일정 수정 중

              <div className={styles.typing}>
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className={styles.chatFoot}>
        <div className={styles.inputBar}>
          <input
            type="text"
            disabled={isInputDisabled}
            placeholder={
              currentStep?.type === 'toggle'
                ? '위 버튼을 눌러 선택해주세요'
                : currentStep?.type === 'dateRange'
                  ? '위 달력에서 날짜를 선택해주세요'
                  : currentStep?.type === 'text'
                    ? '원하는 여행 스타일을 자유롭게 입력해주세요'
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
            disabled={isInputDisabled}
          >
            →
          </button>
        </div>
      </div>
    </div>
  )
};