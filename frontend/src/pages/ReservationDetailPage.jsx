import { useEffect, useMemo, useState } from 'react'

import { Link, useParams } from 'react-router-dom'

import { getItinerary } from '../api/itinerary'

import { getPackageDetail, getPackages } from '../api/packageApi'
import { cancelReservation, getReservation } from '../api/reservationApi'
import AppHeader from '../components/AppHeader.jsx'
import styles from './reservation/reservationDetail.module.css'
import { won } from '../data/packages.js'

const itemTypeLabel = (type) => {
  if (type === 'restaurant') return '음식점'
  if (type === 'hotel' || type === 'accommodation') return '숙소'
  if (type === 'activity') return '액티비티'
  return '관광지'
}

const packageDays = (course = []) =>
  course.map((day, index) => ({
    dayNumber: Number(day.day ?? index + 1),
    date: '',
    path: day.path || [],
    items: (day.items || []).map((item) => ({
      ...item,
      item_type: item.item_type || 'tourism',
    })),
  }))

export default function ReservationDetailPage() {
  const { id } = useParams()
  const [reservation, setReservation] = useState(null)
  const [itinerary, setItinerary] = useState(null)
  const [packageDetails, setPackageDetails] = useState({})
  const [activeItemId, setActiveItemId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError('')

      try {
        const reservationData = await getReservation(id)
        if (cancelled) return
        setReservation(reservationData)
        setActiveItemId(reservationData.items?.[0]?.id ?? null)

        const [itineraryResult, packageResults] = await Promise.all([
          reservationData.itinerary ? getItinerary(reservationData.itinerary).catch(() => null) : Promise.resolve(null),
          (async () => {
            const storedItems = (reservationData.items || []).filter(
              (item) =>
                item.product_type !== 'custom_itinerary' &&
                !String(item.package_id || '')
                  .toUpperCase()
                  .startsWith('CUSTOM-'),
            )
            const needsPackageLookup = storedItems.some((item) => !item.package_db_id)
            const packageResponse = needsPackageLookup ? await getPackages().catch(() => []) : []
            const packageList = Array.isArray(packageResponse) ? packageResponse : packageResponse?.results || []

            return Promise.all(
              storedItems.map(async (item) => {
                const resolvedId =
                  item.package_db_id || packageList.find((pkg) => pkg.package_id === item.package_id)?.id
                return [item.id, resolvedId ? await getPackageDetail(resolvedId).catch(() => null) : null]
              }),
            )
          })(),
        ])

        if (cancelled) return
        setItinerary(itineraryResult)
        setPackageDetails(Object.fromEntries(packageResults))
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError.message || '예약 상세 정보를 불러오지 못했습니다.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [id])

  const activeItem = useMemo(
    () => reservation?.items?.find((item) => item.id === activeItemId) ?? reservation?.items?.[0],
    [activeItemId, reservation],
  )

  const isCustom =
    activeItem?.product_type === 'custom_itinerary' ||
    String(activeItem?.package_id || '')
      .toUpperCase()
      .startsWith('CUSTOM-')
  const packageDetail = activeItem ? packageDetails[activeItem.id] : null
  const days = isCustom
    ? itinerary?.days || []
    : packageDays(activeItem?.schedule?.length ? activeItem.schedule : packageDetail?.course)
  const title = activeItem?.name || packageDetail?.name || itinerary?.title || '예약한 여행 일정'
  const description = isCustom
    ? '사용자가 확정한 일정으로 구성된 자유패키지입니다.'
    : packageDetail?.description || '여행사에서 구성한 제주 여행 패키지입니다.'
  const hotelInfo = isCustom
    ? itinerary?.hotel || activeItem?.accommodation
    : activeItem?.accommodation ||
      (packageDetail?.accommodation_included ? { title: packageDetail.accommodation_name || '숙소 포함' } : null)
  const itineraryLink = reservation?.itinerary ? `/review/${reservation.itinerary}` : '/my/itineraries'
  const itineraryLinkLabel = '내 일정에서 자세히 보기 →'

  const handleCancel = async () => {
    if (!window.confirm('이 예약을 취소할까요? 취소 후에는 되돌릴 수 없습니다.')) return
    setCancelling(true)
    try {
      const updated = await cancelReservation(reservation.id)
      setReservation(updated)
    } catch (cancelError) {
      alert(cancelError.message || '예약을 취소하지 못했습니다.')
    } finally {
      setCancelling(false)
    }
  }

  if (loading) return <div className={styles.message}>예약 일정을 불러오는 중입니다.</div>
  if (error || !reservation)
    return <div className={`${styles.message} ${styles.error}`}>{error || '예약을 찾을 수 없습니다.'}</div>

  return (
    <div className={styles.page}>
      <AppHeader />
      <main className={styles.wrap}>
        <Link className={styles.backLink} to="/my/reservations">
          ← 예약 내역으로 돌아가기
        </Link>

        <header className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 예약 정보 확인</div>
          <h1>예약한 여행 정보를 확인해보세요</h1>
          <p>예약한 내용을 확인하고 관리할 수 있어요.</p>
        </header>

        {reservation.items.length > 1 && (
          <div className={styles.productTabs}>
            {reservation.items.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`${styles.productTab} ${item.id === activeItem?.id ? styles.productTabActive : ''}`}
                onClick={() => setActiveItemId(item.id)}
              >
                {item.name}
              </button>
            ))}
          </div>
        )}

        <article className={styles.card}>
          <div className={styles.topRow}>
            <div>
              <div className={styles.productBadges}>
                <span className={styles.productType}>{isCustom ? '자유패키지' : '여행사 패키지'}</span>
              </div>
              <h2>{title}</h2>
              <p className={styles.sub}>{description}</p>
            </div>
            <strong className={styles.price}>
              {won(activeItem?.price)} <small>/ 1인</small>
            </strong>
          </div>

          <div className={styles.metaRow}>
            <span className={styles.metaItem}>🧾 예약 #{reservation.id}</span>

            <span className={styles.metaItem}>
              📅 예약일 {new Date(reservation.created_at).toLocaleDateString('ko-KR')}
            </span>

            <span className={styles.metaItem}>✓ {reservation.status_display}</span>

            <span className={styles.metaItem}>
              🗓️ {itinerary?.startDate ?? itinerary?.start_date ?? '-'}
              {' ~ '}
              {itinerary?.endDate ?? itinerary?.end_date ?? '-'}
            </span>

            <span className={styles.metaItem}>👤 {activeItem?.quantity || 1}명</span>
          </div>

          <section className={styles.scheduleSummary}>
            <div className={styles.scheduleSummaryHead}>
              <div>
                <h3>여행 일정 요약</h3>
                <p>상세 일정은 내 일정에서 확인할 수 있어요.</p>
              </div>

              <Link to={itineraryLink} className={styles.itineraryLink}>
                {itineraryLinkLabel}
              </Link>
            </div>

            {hotelInfo && (
              <div className={styles.accommodationInfo}>
                <span className={styles.accommodationIcon} aria-hidden="true">
                  🛏
                </span>
                <span className={styles.accommodationCopy}>
                  <small>
                    {isCustom ? '자유일정 숙소' : '패키지 포함 숙소'}
                    {hotelInfo.nights ? ` · ${hotelInfo.nights}박` : ''}
                  </small>
                  <strong>{hotelInfo.title}</strong>
                  {hotelInfo.address && <em>{hotelInfo.address}</em>}
                </span>
                <span className={styles.accommodationIncluded}>숙박 포함</span>
              </div>
            )}

            <div className={styles.scheduleDays}>
              {days.length > 0 ? (
                days.map((day, dayIndex) => (
                  <section className={styles.scheduleDay} key={day.dayNumber ?? dayIndex}>
                    <div className={styles.dayHead}>DAY {day.dayNumber ?? dayIndex + 1}</div>

                    <div className={styles.scheduleStops}>
                      {(day.items || []).map((item, itemIndex) => (
                        <span
                          className={styles.scheduleStop}
                          key={`${item.id ?? item.content_id ?? item.title}-${itemIndex}`}
                        >
                          {item.title}

                          {itemIndex < (day.items || []).length - 1 && <b>→</b>}
                        </span>
                      ))}
                    </div>
                  </section>
                ))
              ) : (
                <p className={styles.sub}>표시할 일정이 없습니다.</p>
              )}
            </div>
          </section>

          <section className={styles.paymentSection}>
            <h3>결제 정보</h3>

            <div className={styles.paymentGrid}>
              <div>
                <span>상품 금액</span>
                <strong>{won(activeItem?.price * (activeItem?.quantity || 1))}</strong>
              </div>

              <div>
                <span>결제 금액</span>
                <strong>{won(reservation.total_price)}</strong>
              </div>

              <div>
                <span>결제 수단</span>
                <strong>{reservation.payment_method}</strong>
              </div>

              <div>
                <span>결제 상태</span>
                <strong>{reservation.status === 'cancelled' ? '예약 취소' : '결제 완료'}</strong>
              </div>
            </div>
          </section>

          {reservation.status === 'cancelled' ? (
            <div className={styles.cancelled}>취소된 예약입니다.</div>
          ) : (
            <button type="button" className={styles.cancelButton} onClick={handleCancel} disabled={cancelling}>
              {cancelling ? '취소 처리 중...' : '예약 취소'}
            </button>
          )}
        </article>
      </main>
    </div>
  )
}
