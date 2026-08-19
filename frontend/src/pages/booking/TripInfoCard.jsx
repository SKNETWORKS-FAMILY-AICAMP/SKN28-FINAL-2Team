import styles from './booking.module.css'
import cx from '../../utils/cx.js'

const WEEKDAY_KO = ['일', '월', '화', '수', '목', '금', '토']

const formatDate = (dateStr) => {
  if (!dateStr) return ''

  const d = new Date(`${dateStr}T00:00:00`)

  if (Number.isNaN(d.getTime())) {
    return dateStr
  }

  const weekday = WEEKDAY_KO[d.getDay()]

  return `${dateStr} (${weekday})`
}

const nightsDaysLabel = (startDate, endDate) => {
  if (!startDate || !endDate) {
    return ''
  }

  const start = new Date(`${startDate}T00:00:00`)
  const end = new Date(`${endDate}T00:00:00`)

  if (
    Number.isNaN(start.getTime()) ||
    Number.isNaN(end.getTime())
  ) {
    return ''
  }

  const nights = Math.round(
    (end - start) /
      (1000 * 60 * 60 * 24)
  )

  if (nights <= 0) {
    return '당일치기'
  }

  return `${nights}박 ${nights + 1}일`
}

/**
 * 여행 정보(기간/인원) 카드.
 *
 * 날짜와 인원의 수정 가능 여부를 각각 관리한다.
 *
 * - 전체 패키지
 *   - 날짜: 수정 가능
 *   - 인원: 수정 가능
 *
 * - LLM 자유일정
 *   - 날짜: 기존 일정의 날짜를 그대로 표시
 *   - 인원: 예약 화면에서 수정 가능
 *
 * - 고정 상태
 *   - 날짜와 인원 모두 값만 표시
 */
export default function TripInfoCard({
  startDate,
  endDate,
  peopleLabel,

  // 날짜 수정 여부
  editableDate = false,

  // 인원 수정 여부
  editablePeople = false,

  onStartDateChange,

  peopleCount,
  onPeopleCountChange,

  minStartDate,
}) {
  const duration = nightsDaysLabel(
    startDate,
    endDate
  )

  return (
    <div
      className={cx(
        styles.card,
        styles.tripInfoCard
      )}
    >
      <h4>여행 정보</h4>

      {/* =========================================================
          여행 기간
          ========================================================= */}
      <div className={styles.tripInfoRow}>
        <div className={styles.tripInfoIcon}>
          📅
        </div>

        <div className={styles.tripInfoBody}>
          <div className={styles.tripInfoLabel}>
            여행 기간
          </div>

          {editableDate ? (
            // ---------------------------------------------------
            // 날짜 수정 가능
            // 전체 패키지
            // ---------------------------------------------------
            <div
              className={
                styles.tripInfoDatePicker
              }
            >
              <input
                type="date"
                value={startDate || ''}
                min={minStartDate}
                onChange={(e) =>
                  onStartDateChange?.(
                    e.target.value
                  )
                }
              />

              {startDate && endDate ? (
                <>
                  <span>
                    ~ {formatDate(endDate)}
                  </span>

                  {duration && (
                    <span
                      className={
                        styles.tripInfoBadge
                      }
                    >
                      {duration}
                    </span>
                  )}
                </>
              ) : (
                <span
                  className={
                    styles.tripInfoHint
                  }
                >
                  출발일을 선택해주세요
                </span>
              )}
            </div>
          ) : (
            // ---------------------------------------------------
            // 날짜 수정 불가
            // LLM 자유일정은 기존 날짜를 그대로 표시
            // ---------------------------------------------------
            <div
              className={
                styles.tripInfoValue
              }
            >
              {startDate && endDate ? (
                <>
                  <span>
                    {formatDate(startDate)} ~{' '}
                    {formatDate(endDate)}
                  </span>

                  {duration && (
                    <span
                      className={
                        styles.tripInfoBadge
                      }
                    >
                      {duration}
                    </span>
                  )}
                </>
              ) : (
                '날짜 정보 없음'
              )}
            </div>
          )}
        </div>
      </div>

      {/* =========================================================
          여행 인원
          ========================================================= */}
      <div className={styles.tripInfoRow}>
        <div className={styles.tripInfoIcon}>
          👤
        </div>

        <div className={styles.tripInfoBody}>
          <div className={styles.tripInfoLabel}>
            여행 인원
          </div>

          {editablePeople ? (
            // ---------------------------------------------------
            // 인원 수정 가능
            // 전체 패키지 + LLM 자유일정
            // ---------------------------------------------------
            <div
              className={
                styles.tripInfoPeopleStepper
              }
            >
              <button
                type="button"
                onClick={() =>
                  onPeopleCountChange?.(
                    Math.max(
                      1,
                      (peopleCount || 1) - 1
                    )
                  )
                }
                aria-label="인원 줄이기"
              >
                −
              </button>

              <span>
                {peopleCount || 1}명
              </span>

              <button
                type="button"
                onClick={() =>
                  onPeopleCountChange?.(
                    Math.min(
                      20,
                      (peopleCount || 1) + 1
                    )
                  )
                }
                aria-label="인원 늘리기"
              >
                +
              </button>
            </div>
          ) : (
            // ---------------------------------------------------
            // 인원 수정 불가
            // ---------------------------------------------------
            <div
              className={
                styles.tripInfoValue
              }
            >
              {peopleLabel ||
                (peopleCount
                  ? `${peopleCount}명`
                  : '인원 정보 없음')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}