import { useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './account/account.module.css'
import cx from '../utils/cx.js'
import AccountHeader from './account/AccountHeader.jsx'
import AccountTabs from './account/AccountTabs.jsx'
import { useReservations } from '../context/ReservationContext.jsx'

const won = (n) => n.toLocaleString('ko-KR') + '원'

const badgeStyle = (status) => {
  if (status === 'cancelled') return styles.badgeCancelled
  if (status === 'confirmed') return styles.badgeConfirmed
  return styles.badgeDraft
}

export default function MyReservationsPage() {
  const { reservations, cancelReservation } = useReservations()
  const [openId, setOpenId] = useState(null)
  const [cancellingId, setCancellingId] = useState(null)
  const [error, setError] = useState('')

  const handleToggle = (id) => {
    setError('')
    setOpenId((prev) => (prev === id ? null : id))
  }

  const handleCancel = async (id) => {
    if (!window.confirm('이 예약을 취소할까요? 취소 후에는 되돌릴 수 없어요.')) return

    setCancellingId(id)
    setError('')
    try {
      await cancelReservation(id)
    } catch (e) {
      setError(e.message || '예약 취소에 실패했어요. 잠시 후 다시 시도해주세요.')
    } finally {
      setCancellingId(null)
    }
  }

  return (
    <div className={styles.page}>
      <AccountHeader />
      <div className={styles.wrap}>
        <AccountTabs active="/my/reservations" />

        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 예약 내역</div>
          <h1>예약 내역</h1>
          <p>예약 요청한 패키지 내역을 확인하고, 필요하면 취소할 수 있어요.</p>
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
            reservations.map((r) => {
              const isOpen = openId === r.id
              const isCancelled = r.status === 'cancelled'
              const isCancelling = cancellingId === r.id

              return (
                <div key={r.id} className={styles.reservationBlock}>
                  <button
                    className={cx(styles.listItem, styles.listItemButton)}
                    onClick={() => handleToggle(r.id)}
                    aria-expanded={isOpen}
                  >
                    <div className={styles.listThumb}>🧾</div>
                    <div className={styles.listInfo}>
                      <h5>예약 #{r.id.toString().slice(-6)}</h5>
                      <p>
                        {r.items.map((i) => i.name).join(', ')} · {r.payment_method}
                      </p>
                      <span className={cx(styles.badge, badgeStyle(r.status))}>{r.status_display}</span>
                    </div>
                    <div className={styles.listMeta}>
                      <div className={styles.price}>{won(r.total_price)}</div>
                      <div className={styles.sub}>{new Date(r.created_at).toLocaleDateString('ko-KR')}</div>
                      <div className={styles.detailToggle}>{isOpen ? '접기 ▴' : '상세보기 ▾'}</div>
                    </div>
                  </button>

                  {isOpen && (
                    <div className={styles.reservationDetail}>
                      <div className={styles.detailRow}>
                        <span className={styles.detailLabel}>예약 항목</span>
                      </div>
                      {r.items.map((item, i) => (
                        <div className={styles.detailItemRow} key={i}>
                          <span> {item.name}</span>

                          <span>
                            {won(item.price)} × {item.quantity}개
                          </span>
                        </div>
                      ))}
                      <div className={styles.detailDivider}></div>
                      <div className={styles.detailRow}>
                        <span className={styles.detailLabel}>결제 수단</span>
                        <span>{r.payment_method}</span>
                      </div>
                      <div className={styles.detailRow}>
                        <span className={styles.detailLabel}>예약 일시</span>
                        <span>{new Date(r.created_at).toLocaleString('ko-KR')}</span>
                      </div>
                      <div className={styles.detailRow}>
                        <span className={styles.detailLabel}>총 결제 금액</span>
                        <span className={styles.detailTotal}>{won(r.total_price)}</span>
                      </div>

                      {error && cancellingId === null && (
                        <div className={styles.detailError}>{error}</div>
                      )}

                      {!isCancelled && (
                        <button
                          className={styles.cancelBtn}
                          onClick={() => handleCancel(r.id)}
                          disabled={isCancelling}
                        >
                          {isCancelling ? '취소 처리 중…' : '예약 취소'}
                        </button>
                      )}
                      {isCancelled && <div className={styles.cancelledNotice}>이미 취소된 예약이에요.</div>}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}