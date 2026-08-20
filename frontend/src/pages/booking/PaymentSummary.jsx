import styles from './booking.module.css'
import cx from '../../utils/cx.js'
import { won } from '../../data/packages.js'

export default function PaymentSummary({
  items = [],
  totalPrice = 0,
  peopleCount = 1,
  usePeopleCount = false,
  onConfirm,
  submitting,
}) {
  return (
    <div className={cx(styles.card, styles.paySummary)}>
      <h4>결제 정보</h4>

      <div className={styles.payTotalLabel}>총 결제 금액</div>
      <div className={styles.payTotal}>{won(totalPrice)}</div>

      {items.map((item) => (
        <div className={styles.payRow} key={item.cartId ?? item.package.id}>
          <span className={styles.k}>
            {item.package.name
              .replace(/\d{1,3}(,\d{3})*원/g, '')
              .trim()}
          </span>

          <span className={styles.v}>
            {won(Number(item.package.price) * (usePeopleCount ? peopleCount : item.quantity))}
          </span>
        </div>
      ))}

      <div className={styles.payDivider}></div>

      <div className={styles.payRow}>
        <span
          className={styles.k}
          style={{ fontWeight: 700, color: 'var(--ink)' }}
        >
          총 합계
        </span>
        <span
          className={styles.v}
          style={{ color: 'var(--green-deep)', fontSize: 15 }}
        >
          {won(totalPrice)}
        </span>
      </div>

      <div className={styles.payMethod} style={{ marginTop: 14 }}>
        <div>
          <div className={styles.label}>결제 수단</div>
          <div className={styles.val}>
            신용카드 (**** **** **** 1234)
          </div>
        </div>
        <button className={styles.change}>변경</button>
      </div>

      <button
        className={cx(styles.btn, styles.primary, styles.wide)}
        onClick={onConfirm}
        disabled={items.length === 0 || submitting}
      >
        {submitting ? '결제 처리 중…' : '🔒 예약 및 결제하기'}
      </button>

      <div className={styles.terms}>
        결제 시 약관에 동의한 것으로 간주됩니다.
      </div>
    </div>
  )
}
