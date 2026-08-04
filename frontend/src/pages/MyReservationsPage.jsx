import { Link } from 'react-router-dom'
import styles from './account/account.module.css'
import cx from '../utils/cx.js'
import AccountHeader from './account/AccountHeader.jsx'
import AccountTabs from './account/AccountTabs.jsx'
import { useReservations } from '../context/ReservationContext.jsx'

const won = (n) => n.toLocaleString('ko-KR') + '원'

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
          <p>예약 요청한 패키지 내역을 확인할 수 있어요.</p>
        </div>

        <div className={styles.card}>
          {reservations.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.icon}>🧾</div>
              <h4>아직 예약 내역이 없어요</h4>
              <p>예약/결제 화면에서 패키지를 예약하면 여기에 기록돼요.</p>
              <Link to="/booking" className={cx(styles.btn, styles.primary)}>
                예약하러 가기 →
              </Link>
            </div>
          ) : (
            reservations.map((r) => (
              <div className={styles.listItem} key={r.id}>
                <div className={styles.listThumb}>🧾</div>
                <div className={styles.listInfo}>
                  <h5>예약 #{r.id.toString().slice(-6)}</h5>
                  <p>
                    {r.items.map((i) => i.name).join(', ')} · {r.payment_method}
                  </p>
                  <span className={cx(styles.badge, styles.badgeConfirmed)}>{r.status_display}</span>
                </div>
                <div className={styles.listMeta}>
                  <div className={styles.price}>{won(r.total_price)}</div>
                  <div className={styles.sub}>{new Date(r.created_at).toLocaleDateString('ko-KR')}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
