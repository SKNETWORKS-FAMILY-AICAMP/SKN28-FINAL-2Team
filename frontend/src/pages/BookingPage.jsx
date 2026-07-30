import { useState } from 'react'
import { Link, useLocation } from "react-router-dom";
import styles from './booking/booking.module.css'
import cx from '../utils/cx.js'
import AppHeader from './booking/AppHeader.jsx'
import PackageList from './booking/PackageList.jsx'
import PaymentSummary from './booking/PaymentSummary.jsx'
import { PACKAGES } from '../data/packages.js'
import { useBookmarks } from '../context/BookmarkContext.jsx'
import { useReservations } from '../context/ReservationContext.jsx'

export default function BookingPage() {
  const { addReservation } = useReservations()
  const { state } = useLocation();
  const [selected, setSelected] = useState([1, 2]) // 오션뷰 힐링 숙소 + 렌터카 3일 기본 선택
  const [visibility, setVisibility] = useState('비공개')
  const [submitting, setSubmitting] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const { isBookmarked, toggle: toggleBookmark } = useBookmarks()
  const itineraryId = state?.itineraryId;
  const toggle = (id) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const chosen = PACKAGES.filter((p) => selected.includes(p.id))
  const total = chosen.reduce((sum, p) => sum + p.price, 0)

  const handleConfirm = () => {
    setSubmitting(true)
    setTimeout(() => {
      // 실제로는 POST /api/reservations/ 호출 — 아직 연결 전이라 ReservationContext에 바로 기록
      addReservation(
        chosen.map((p) => ({ packageId: p.id, name: p.name, price: p.price })),
        '신용카드 (**** **** **** 1234)'
      )
      setSubmitting(false)
      setConfirmed(true)
    }, 1200)
  }

  return (
    <div className={styles.page}>
      <AppHeader />

      <div className={styles.wrap}>
        <Link to={`/review/${itineraryId}`} className={styles.backLink}>
          ← 일정으로 돌아가기
        </Link>

        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 예약 및 저장</div>
          <h1>{confirmed ? '예약이 완료됐어요!' : '마지막이에요, 예약을 확정해주세요'}</h1>
          <p>
            {confirmed
              ? '결제 확인 메일을 보내드렸어요. 즐거운 제주 여행 되세요 🌿'
              : '제주 2박 3일 힐링 여행에 함께할 패키지를 선택하고 결제를 진행하세요.'}
          </p>
        </div>

        {confirmed ? (
          <div className={styles.successCard}>
            <div className={styles.successBadge}>✓</div>
            <h2>예약이 확정됐어요 🎉</h2>
            <p>
              제주 2박 3일 힐링 여행 예약이 완료됐어요.
              <br />
              "예약 내역"에서 언제든 다시 확인할 수 있어요.
            </p>
            <div className={styles.successMeta}>
              <div className={styles.row}>
                <span className={styles.k}>여행 일정</span>
                <span className={styles.v}>2024.07.25 – 07.27 · 2박 3일</span>
              </div>
              <div className={styles.row}>
                <span className={styles.k}>결제 금액</span>
                <span className={styles.v}>{total.toLocaleString('ko-KR')}원</span>
              </div>
              <div className={styles.row}>
                <span className={styles.k}>공개 설정</span>
                <span className={styles.v}>{visibility}</span>
              </div>
            </div>
            <div style={{ marginTop: 26, display: 'flex', gap: 10, justifyContent: 'center' }}>
              <Link to="/my/reservations" className={cx(styles.btn, styles.ghost)}>
                예약 내역 보기
              </Link>
              <Link to="/" className={cx(styles.btn, styles.primary)}>
                홈으로
              </Link>
            </div>
          </div>
        ) : (
          <div className={styles.shell}>
            <div>
              <PackageList
                selected={selected}
                onToggle={toggle}
                isBookmarked={isBookmarked}
                onToggleBookmark={toggleBookmark}
              />

              <div className={cx(styles.card, styles.saveCard)}>
                <h4>일정 저장</h4>
                <div className={styles.saveRow}>
                  <button className={cx(styles.btn, styles.ghost, styles.sm)}>💾 내 여행으로 저장</button>
                  <div className={styles.visibility}>
                    공개 설정
                    <b
                      style={{ cursor: 'pointer' }}
                      onClick={() => setVisibility((v) => (v === '비공개' ? '공개' : '비공개'))}
                    >
                      {visibility}
                    </b>
                  </div>
                </div>
              </div>
            </div>

            <PaymentSummary selected={selected} onConfirm={handleConfirm} submitting={submitting} />
          </div>
        )}
      </div>
    </div>
  )
}
