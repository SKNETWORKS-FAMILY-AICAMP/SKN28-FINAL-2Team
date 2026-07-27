import { Link, useNavigate } from 'react-router-dom'
import styles from './review/review.module.css'
import cx from '../utils/cx.js'
import AppHeader from './review/AppHeader.jsx'
import { DayNav, DayColumns, useDayNav } from './review/ItineraryOverview.jsx'
import TripSummary from './review/TripSummary.jsx'

export default function ReviewPage() {
  const { activeDay, selectDay, dayRefs } = useDayNav()
  const navigate = useNavigate()

  return (
    <div className={styles.page}>
      <AppHeader />

      <div className={styles.wrap}>
        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 최종 일정 확인</div>
          <h1>확정 전, 마지막으로 검토해주세요</h1>
          <p>일정과 예상 비용을 확인하고, 이 일정으로 예약을 진행할 수 있어요.</p>
        </div>

        <div className={styles.shell}>
          <DayNav activeDay={activeDay} onSelect={selectDay} />

          <div className={styles.mainCard}>
            <div className={styles.topRow}>
              <div>
                <h2>제주 2박 3일 힐링 여행</h2>
                <div className={styles.sub}>부모님과 함께</div>
              </div>
              <div className={styles.actionRow}>
                <button className={cx(styles.btn, styles.ghost, styles.sm)}>📤 공유하기</button>
                <button className={cx(styles.btn, styles.ghost, styles.sm)}>📄 PDF 다운로드</button>
                <Link to="/itinerary" className={cx(styles.btn, styles.ghost, styles.sm)}>
                  ✏️ 일정 수정하기
                </Link>
              </div>
            </div>

            <div className={styles.metaRow}>
              <div className={styles.metaItem}>📅 2박 3일</div>
              <div className={styles.metaItem}>👥 2명</div>
              <div className={styles.metaItem}>🍃 힐링 여행</div>
              <div className={styles.metaItem}>💰 1인당 50만원</div>
            </div>

            <div className={styles.grid}>
              <DayColumns dayRefs={dayRefs} />
              <TripSummary />
            </div>
          </div>
        </div>

        <div className={styles.bottomActions}>
          <Link to="/itinerary" className={cx(styles.btn, styles.ghost)}>
            이전 단계로
          </Link>
          <button className={cx(styles.btn, styles.primary)} onClick={() => navigate('/booking')}>
            이 일정으로 확정하기 →
          </button>
        </div>
      </div>
    </div>
  )
}
