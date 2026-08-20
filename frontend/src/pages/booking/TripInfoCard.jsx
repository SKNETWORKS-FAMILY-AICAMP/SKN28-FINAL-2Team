import styles from './booking.module.css'
import cx from '../../utils/cx.js'

const formatDate = (date) => date?.replaceAll('-', '.') || ''

export default function TripInfoCard({
  startDate,
  endDate,
  peopleCount,
  minStartDate,
  dateLocked = false,
  onStartDateChange,
  onPeopleCountChange,
}) {
  const duration = startDate && endDate
    ? Math.max(0, Math.round((new Date(`${endDate}T00:00:00`) - new Date(`${startDate}T00:00:00`)) / 86400000))
    : 0

  return (
    <section className={cx(styles.card, styles.tripInfoCard)}>
      <h4>예약 정보</h4>

      <div className={styles.tripInfoRow}>
        <span className={styles.tripInfoIcon}>📅</span>
        <div>
          <div className={styles.tripInfoLabel}>여행 기간</div>
          <div className={styles.tripInfoValue}>
            {dateLocked ? (
              <span>{formatDate(startDate)} ~ {formatDate(endDate)}</span>
            ) : (
              <>
                <input
              type="date"
              aria-label="출발일"
              value={startDate}
              min={minStartDate}
              onChange={(event) => onStartDateChange(event.target.value)}
            />
                <span>~ {formatDate(endDate)}</span>
              </>
            )}
            <span className={styles.tripInfoBadge}>
              {duration ? `${duration}박 ${duration + 1}일` : '당일치기'}
            </span>
          </div>
        </div>
      </div>

      <div className={styles.tripInfoRow}>
        <span className={styles.tripInfoIcon}>👤</span>
        <div>
          <div className={styles.tripInfoLabel}>여행 인원</div>
          <div className={styles.tripInfoPeopleStepper}>
            <button
              type="button"
              aria-label="인원 줄이기"
              onClick={() => onPeopleCountChange(Math.max(1, peopleCount - 1))}
            >
              −
            </button>
            <span>{peopleCount}명</span>
            <button
              type="button"
              aria-label="인원 늘리기"
              onClick={() => onPeopleCountChange(Math.min(20, peopleCount + 1))}
            >
              +
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
