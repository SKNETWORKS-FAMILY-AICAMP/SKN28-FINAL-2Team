import styles from './review.module.css'

const COSTS = [
  { label: '숙소', amount: 159000 },
  { label: '렌터카', amount: 89700 },
  { label: '액티비티', amount: 70000 },
  { label: '식비', amount: 90000 },
  { label: '기타', amount: 30000 },
]

const TOTAL = COSTS.reduce((sum, c) => sum + c.amount, 0)

const won = (n) => n.toLocaleString('ko-KR') + '원'

export default function TripSummary() {
  return (
    <div className={styles.summary}>
      <h4>여행 요약</h4>

      <div className={styles.mapPanel}>
        <svg viewBox="0 0 220 150" xmlns="http://www.w3.org/2000/svg">
          <rect width="220" height="150" fill="#CDE9F2" />
          <path
            d="M25 95c-5-22 14-42 44-46 22-3 34 6 51 3 22-4 44 3 57 19 10 12 9 31-5 41-16 13-42 15-67 10-25-4-42-1-59-10-13-7-19-10-21-17z"
            fill="var(--green-soft)"
            stroke="#1B211D"
            strokeWidth="2.5"
          />
          <path
            d="M44 86c7-3 16 4 25 1 10-3 15-11 25-10 12 1 15 10 25 12 9 1 17-4 25 0"
            fill="none"
            stroke="#2E9E62"
            strokeWidth="2"
            strokeDasharray="1 6"
            strokeLinecap="round"
          />
          <circle cx="44" cy="86" r="6" fill="#2E9E62" stroke="#1B211D" strokeWidth="1.5" />
          <circle cx="69" cy="88" r="6" fill="#2E9E62" stroke="#1B211D" strokeWidth="1.5" />
          <circle cx="94" cy="78" r="6" fill="#2E9E62" stroke="#1B211D" strokeWidth="1.5" />
          <circle cx="119" cy="90" r="6" fill="#2E9E62" stroke="#1B211D" strokeWidth="1.5" />
          <circle cx="144" cy="90" r="6" fill="#F4B740" stroke="#1B211D" strokeWidth="1.5" />
        </svg>
      </div>

      <div className={styles.summaryLabel}>여행 기간</div>
      <div className={styles.summaryRow}>
        <span className={styles.v}>2024.07.25(목) – 07.27(토) · 2박 3일</span>
      </div>

      <div className={styles.summaryDivider}></div>

      <div className={styles.summaryLabel}>예상 비용 (1인 기준)</div>
      {COSTS.map((c) => (
        <div className={styles.summaryRow} key={c.label}>
          <span className={styles.k}>{c.label}</span>
          <span className={styles.v}>{won(c.amount)}</span>
        </div>
      ))}

      <div className={styles.summaryDivider}></div>

      <div className={styles.summaryTotal}>
        <span className={styles.k}>총 합계</span>
        <span className={styles.v}>{won(TOTAL)}</span>
      </div>
    </div>
  )
}
