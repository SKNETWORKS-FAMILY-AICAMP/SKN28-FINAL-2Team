import { Link } from 'react-router-dom'

import styles from './account/account.module.css'
import cx from '../utils/cx.js'
import AccountHeader from './account/AccountHeader.jsx'
import AccountTabs from './account/AccountTabs.jsx'
import { useReservations } from '../context/ReservationContext.jsx'
import { won } from '../data/packages.js'

const badgeStyle = (status) => {
  if (status === 'cancelled') return styles.badgeCancelled
  if (status === 'confirmed') return styles.badgeConfirmed
  return styles.badgeDraft
}

export default function MyReservationsPage() {
  const { reservations } = useReservations()

  return (
    <div className={styles.page}>
      <AccountHeader />
      <div className={styles.wrap}>
        <AccountTabs active="/my/reservations" />

        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 예약 내역</div>
          <h1>예약 내역</h1>
          <p>예약한 상품을 선택하면 전체 일정과 동선을 확인할 수 있어요.</p>
        </div>

        <div className={styles.card}>
          {reservations.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.icon}>🧾</div>
              <h4>아직 예약 내역이 없어요</h4>
              <p>패키지 또는 자유일정을 예약하면 여기에 기록돼요.</p>
              <Link to="/packages" className={cx(styles.btn, styles.primary)}>
                패키지 둘러보기 →
              </Link>
            </div>
          ) : (
            reservations.map((reservation) => {
              const firstItem = reservation.items?.[0]
              const extraCount = Math.max((reservation.items?.length || 0) - 1, 0)
              const itemSummary = firstItem
                ? `${firstItem.display_name || firstItem.name}${extraCount ? ` 외 ${extraCount}개` : ''}`
                : '예약한 여행 상품'
              const tripInfo = [
                firstItem?.option_date?.replaceAll('-', '.'),
                firstItem?.option_people && `${firstItem.option_people}명`,
              ].filter(Boolean).join(' · ') || '예약한 여행'
              const isCustom =
                firstItem?.product_type === 'custom_itinerary' ||
                String(firstItem?.package_id || '').toUpperCase().startsWith('CUSTOM-')

              return (
                <Link
                  key={reservation.id}
                  to={`/my/reservations/${reservation.id}`}
                  className={styles.listItem}
                >
                  <div className={styles.listThumb}>
                    {firstItem?.thumbnail_url ? (
                      <img
                        src={firstItem.thumbnail_url}
                        alt={firstItem.display_name || firstItem.name}
                        className={styles.listThumbImage}
                      />
                    ) : (
                      isCustom ? '🏝️' : '🧳'
                    )}
                  </div>
                  <div className={styles.listInfo}>
                    <h5>{itemSummary}</h5>
                    <p>{tripInfo}</p>
                    <span className={cx(styles.badge, badgeStyle(reservation.status))}>
                      {reservation.status_display}
                    </span>
                  </div>
                  <div className={styles.listMeta}>
                    <div className={styles.price}>{won(reservation.total_price)}</div>
                    <div className={styles.sub}>
                      {new Date(reservation.created_at).toLocaleDateString('ko-KR')}
                    </div>
                    <div className={styles.detailToggle}>일정 보기 →</div>
                  </div>
                </Link>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
