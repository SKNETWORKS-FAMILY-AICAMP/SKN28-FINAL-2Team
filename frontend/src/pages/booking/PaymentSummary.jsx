import styles from './booking.module.css'
import cx from '../../utils/cx.js'
import { PACKAGES } from './PackageList.jsx'

const won = (n) => n.toLocaleString('ko-KR') + '원'

export default function PaymentSummary({ selected, onConfirm, submitting }) {
  const chosen = PACKAGES.filter((p) => selected.includes(p.id))
  const total = chosen.reduce((sum, p) => sum + p.price, 0)

  return (
    <div className={cx(styles.card, styles.paySummary)}>
      <h4>결제 정보</h4>

      <div className={styles.payTotalLabel}>총 결제 금액</div>
      <div className={styles.payTotal}>{won(total)}</div>

      {PACKAGES.map((p) => (
        <div className={styles.payRow} key={p.id}>
          <span className={styles.k}>{p.title.split(' ')[0]}</span>
          <span className={styles.v}>{selected.includes(p.id) ? won(p.price) : '—'}</span>
        </div>
      ))}
      <div className={styles.payRow}>
        <span className={styles.k}>할인 쿠폰</span>
        <span className={cx(styles.v, styles.discount)}>-0원</span>
      </div>

      <div className={styles.payDivider}></div>

      <div className={styles.payRow}>
        <span className={styles.k} style={{ fontWeight: 700, color: 'var(--ink)' }}>
          총 합계
        </span>
        <span className={styles.v} style={{ color: 'var(--green-deep)', fontSize: 15 }}>
          {won(total)}
        </span>
      </div>

      <div className={styles.payMethod} style={{ marginTop: 14 }}>
        <div>
          <div className={styles.label}>결제 수단</div>
          <div className={styles.val}>신용카드 (**** **** **** 1234)</div>
        </div>
        <button className={styles.change}>변경</button>
      </div>

      <button
        className={cx(styles.btn, styles.primary, styles.wide)}
        onClick={onConfirm}
        disabled={chosen.length === 0 || submitting}
      >
        {submitting ? '결제 처리 중…' : '🔒 예약 및 결제하기'}
      </button>
      <div className={styles.terms}>결제 시 약관에 동의한 것으로 간주됩니다.</div>
    </div>
  )
}
