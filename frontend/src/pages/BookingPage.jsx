import {  useEffect, useState } from 'react'
import { Link, useLocation } from "react-router-dom";
import styles from './booking/booking.module.css'
import cx from '../utils/cx.js'
import AppHeader from '../components/AppHeader.jsx'
import PackageList from './booking/PackageList.jsx'
import PaymentSummary from './booking/PaymentSummary.jsx'
import TripInfoCard from './booking/TripInfoCard.jsx'
import { useBookmarks } from '../context/BookmarkContext.jsx'
import { useReservations } from '../context/ReservationContext.jsx'
import { useCart } from '../context/CartContext.jsx'
import { useItineraries } from '../context/ItineraryContext.jsx'
import { won } from '../data/packages.js'

const toDateInputValue = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const addDays = (dateValue, days) => {
  const date = new Date(`${dateValue}T00:00:00`)
  date.setDate(date.getDate() + days)
  return toDateInputValue(date)
}

export default function BookingPage() {
  const { addReservation } = useReservations()
  const { refresh: refreshItineraries } = useItineraries()
  const { state } = useLocation();
  const bookingSource = state?.bookingSource || 'itinerary'
  const initialSelected =
    bookingSource === 'package' && Array.isArray(state?.packageIds)
      ? state.packageIds
      : bookingSource === 'custom-itinerary' && Array.isArray(state?.packages)
        ? state.packages.map((item) => item.id)
      : [1, 2]
  const [selected, setSelected] = useState(initialSelected)
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
  const isCustomBooking = bookingSource === 'custom-itinerary'
  const isPackageBooking = bookingSource === 'package'
  const isStandalonePackageBooking = isPackageBooking && !itineraryId
  const usesPeopleCount = isStandalonePackageBooking || Boolean(itineraryId)
  const minStartDate = addDays(toDateInputValue(new Date()), 1)
  const [startDate, setStartDate] = useState(state?.startDate || minStartDate)
  const [peopleCount, setPeopleCount] = useState(state?.peopleCount || 1)
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
  const durationDays = Math.max(
    Number(chosen[0]?.durationDays ?? chosen[0]?.duration_days ?? 1),
    1,
  )
  const endDate = itineraryId
    ? state?.endDate || startDate
    : startDate ? addDays(startDate, durationDays - 1) : ''

  const total = chosenItems.reduce(
    (sum, item) =>
      sum + Number(item.package.price) * (usesPeopleCount ? peopleCount : item.quantity),
    0
  )

  const handleConfirm = async () => {
  setSubmitting(true)

  try {
    const reservation = await addReservation(
      '신용카드 (**** **** **** 1234)',
      {
        packageIds: isCartBooking
          || isCustomBooking
          ? undefined
          : chosen.map((p) => p.id),
        cartItemIds: isCartBooking
          ? chosenItems.map((item) => item.cartId)
          : undefined,
        itineraryId,
        startDate: isStandalonePackageBooking ? startDate : undefined,
        peopleCount: usesPeopleCount ? peopleCount : undefined,
      }
    )

    setConfirmedTotal(
      Number(reservation.total_price ?? total)
    )

    setConfirmedReservation(reservation)
    setConfirmed(true)

    if (itineraryId || isStandalonePackageBooking) {
      try {
        await refreshItineraries()
      } catch (error) {
        console.error('예약 후 일정 목록 새로고침 실패:', error)
      }
    }

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
      ?.map((item) => item.display_name || item.name)
      .filter(Boolean) ?? []

  const confirmedTitle =
    confirmedItemNames.length > 0
      ? confirmedItemNames.join(', ')
      : '예약한 제주 패키지'

  const confirmedItem = confirmedReservation?.items?.[0]
  const confirmedStartDate = confirmedItem?.option_date || startDate
  const confirmedDate = confirmedStartDate
    ? `${confirmedStartDate.replaceAll('-', '.')} ~ ${endDate.replaceAll('-', '.')}`
    : ''
  const confirmedPeople = confirmedItem?.option_people || confirmedItem?.quantity

  return (
    <div className={styles.page}>
      <AppHeader />

      <div className={styles.wrap}>
        {!confirmed && (
          <Link
            to={itineraryId ? `/review/${itineraryId}` : '/packages'}
            className={styles.backLink}
          >
            ← {itineraryId ? '일정으로 돌아가기' : '패키지로 돌아가기'}
          </Link>
        )}

        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 예약 및 결제</div>

          <h1>
            {confirmed
              ? '결제가 완료됐어요!'
              : '예약 전 마지막으로 확인해주세요'}
          </h1>

          <p>
            {confirmed
              ? '예약이 정상적으로 확정되었습니다.'
              : bookingSource === 'package'
                ? '선택한 패키지와 결제 금액을 확인해주세요.'
                : bookingSource === 'custom-itinerary'
                  ? '선택한 일정과 결제 금액을 확인해주세요.'
                  : bookingSource === 'cart'
                    ? '장바구니에 담은 상품과 결제 금액을 확인해주세요.'
                    : '선택한 여행 상품과 결제 금액을 확인해주세요.'}
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
                <span className={styles.v}>{won(confirmedTotal)}</span>
              </div>
              <div className={styles.row}>
                <span className={styles.k}>인원</span>
                <span className={styles.v}>{confirmedPeople || 1}명</span>
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
              {usesPeopleCount && (
                <TripInfoCard
                  startDate={startDate}
                  endDate={endDate}
                  peopleCount={peopleCount}
                  minStartDate={minStartDate}
                  dateLocked={Boolean(itineraryId)}
                  onStartDateChange={setStartDate}
                  onPeopleCountChange={setPeopleCount}
                />
              )}
              </div>

              <PaymentSummary
                items={chosenItems}
                totalPrice={total}
                peopleCount={peopleCount}
                usePeopleCount={usesPeopleCount}
                onConfirm={handleConfirm}
                submitting={submitting}
              />
            </div>
          )}
        </div>
      </div>
    )
  }
