import {  useEffect, useState } from 'react'
import { Link, useLocation } from "react-router-dom";
import styles from './booking/booking.module.css'
import cx from '../utils/cx.js'
import AppHeader from './booking/AppHeader.jsx'
import PackageList from './booking/PackageList.jsx'
import PaymentSummary from './booking/PaymentSummary.jsx'
import { useBookmarks } from '../context/BookmarkContext.jsx'
import { useReservations } from '../context/ReservationContext.jsx'
import { useCart } from '../context/CartContext.jsx'

export default function BookingPage() {
  const { addReservation } = useReservations()
  const { state } = useLocation();
  const bookingSource = state?.bookingSource || 'itinerary'
  const initialSelected =
    bookingSource === 'package' && Array.isArray(state?.packageIds)
      ? state.packageIds
      : [1, 2]
  const [selected, setSelected] = useState(initialSelected)
  const [visibility, setVisibility] = useState('비공개')
  const [submitting, setSubmitting] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const { isBookmarked, toggle: toggleBookmark } = useBookmarks()
  const { cartPackages, refreshCart } = useCart()
  const [confirmedTotal, setConfirmedTotal] = useState(0)
  const [confirmedReservation, setConfirmedReservation] = useState(null)
  const itineraryId = state?.itineraryId;
  const toggle = (id) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const isCartBooking = bookingSource === 'cart'
  useEffect(() => {
    if (isCartBooking) {
      setSelected(
        cartPackages.map((item) => item.package.id)
      )
    }
  }, [isCartBooking, cartPackages])
  const directPackages = Array.isArray(state?.packages)
    ? state.packages
    : []

  const packageItems = directPackages.map((p) => ({
    cartId: `package-${p.id}`,
    package: p,
    quantity: 1,
  }))
  const bookingItems = isCartBooking ? cartPackages : packageItems
  const chosenItems = bookingItems.filter((item) =>
      selected.includes(item.package.id)
  )
  const chosen = chosenItems.map((item) => item.package)

  const total = chosenItems.reduce(
    (sum, item) =>
      sum + Number(item.package.price) * item.quantity,
    0
  )

  const handleConfirm = async () => {
  setSubmitting(true)

  try {
    const reservation = await addReservation(
      '신용카드 (**** **** **** 1234)',
      {
        packageIds: isCartBooking
          ? undefined
          : chosen.map((p) => p.id),
        cartItemIds: isCartBooking
          ? chosenItems.map((item) => item.cartId)
          : undefined,
        itineraryId,
      }
    )

    setConfirmedTotal(
      Number(reservation.total_price ?? total)
    )

    setConfirmedReservation(reservation)
    setConfirmed(true)

    if (isCartBooking) {
      await refreshCart()
    }
  } catch (error) {
    console.error('예약 생성 실패:', error)
    alert(
      error.message ||
        '예약에 실패했어요. 다시 시도해주세요.'
    )
  } finally {
    setSubmitting(false)
  }
}
  const confirmedItemNames =
    confirmedReservation?.items
      ?.map((item) => item.name)
      .filter(Boolean) ?? []

  const confirmedTitle =
    confirmedItemNames.length > 0
      ? confirmedItemNames.join(', ')
      : '예약한 제주 패키지'

  const confirmedDate =
    confirmedReservation?.created_at
      ? new Date(confirmedReservation.created_at).toLocaleDateString('ko-KR')
      : ''

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
              {confirmedTitle} 예약이 완료됐어요.
              <br />
              "예약 내역"에서 언제든 다시 확인할 수 있어요.
            </p>
            <div className={styles.successMeta}>
              <div className={styles.row}>
                <span className={styles.k}>예약 일자</span>
                <span className={styles.v}>
                  {confirmedDate || '예약 완료'}
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.k}>결제 금액</span>
                <span className={styles.v}>{confirmedTotal.toLocaleString('ko-KR')}원</span>
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
                items={bookingItems}
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

            <PaymentSummary
              items={chosenItems}
              totalPrice={total}
              onConfirm={handleConfirm}
              submitting={submitting}
            />
          </div>
        )}
      </div>
    </div>
  )
}
