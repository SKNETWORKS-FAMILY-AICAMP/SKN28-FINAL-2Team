import styles from './itinerary.module.css'
import cx from '../../utils/cx.js'

const PACKAGES = [
  { icon: '🏨', rating: '★ 4.6 (321)', title: '오션뷰 힐링 숙소', price: '159,000원 ~' },
  { icon: '🚗', rating: '★ 4.7 (532)', title: '렌터카 3일', price: '89,700원 ~' },
  { icon: '🐴', rating: '★ 4.6 (218)', title: '제주 승마 체험', price: '70,000원 ~' },
]

export default function MapPanel() {
  return (
    <div className={styles.mapCol}>
      <div className={styles.mapHead}>
        <h4>🗺️ 전체 동선</h4>
        <div className={styles.mapToggle}>
          <button className={styles.mapToggleActive}>지도</button>
          <button>목록</button>
        </div>
      </div>

      <div className={styles.mapPanel}>
        <svg viewBox="0 0 300 220" xmlns="http://www.w3.org/2000/svg">
          <rect width="300" height="220" fill="#CDE9F2" />
          <path
            d="M35 130c-6-30 20-58 60-64 30-4 46 8 70 4 30-6 60 4 78 26 14 17 12 42-6 56-22 18-58 20-92 14-34-6-58-2-80-14-18-10-26-14-30-22z"
            fill="var(--green-soft)"
            stroke="#1B211D"
            strokeWidth="3"
          />
          <path
            d="M60 118c10-4 22 6 34 2 14-5 20-16 34-14 16 2 20 14 34 16 12 2 24-6 34 0"
            fill="none"
            stroke="#2E9E62"
            strokeWidth="2.5"
            strokeDasharray="1 7"
            strokeLinecap="round"
          />
          <circle cx="60" cy="118" r="9" fill="#2E9E62" stroke="#1B211D" strokeWidth="2" />
          <text x="60" y="121.5" fontFamily="IBM Plex Mono" fontSize="9" fill="#fff" textAnchor="middle" fontWeight="700">1</text>
          <circle cx="94" cy="120" r="9" fill="#2E9E62" stroke="#1B211D" strokeWidth="2" />
          <text x="94" y="123.5" fontFamily="IBM Plex Mono" fontSize="9" fill="#fff" textAnchor="middle" fontWeight="700">2</text>
          <circle cx="128" cy="106" r="9" fill="#2E9E62" stroke="#1B211D" strokeWidth="2" />
          <text x="128" y="109.5" fontFamily="IBM Plex Mono" fontSize="9" fill="#fff" textAnchor="middle" fontWeight="700">3</text>
          <circle cx="162" cy="122" r="9" fill="#2E9E62" stroke="#1B211D" strokeWidth="2" />
          <text x="162" y="125.5" fontFamily="IBM Plex Mono" fontSize="9" fill="#fff" textAnchor="middle" fontWeight="700">4</text>
          <circle cx="196" cy="122" r="9" fill="#F4B740" stroke="#1B211D" strokeWidth="2" />
          <text x="196" y="125.5" fontFamily="IBM Plex Mono" fontSize="9" fill="#1B211D" textAnchor="middle" fontWeight="700">5</text>
          <circle cx="80" cy="70" r="3" fill="#fff" opacity=".8" />
          <circle cx="220" cy="60" r="4" fill="#fff" opacity=".7" />
          <circle cx="240" cy="150" r="3" fill="#fff" opacity=".8" />
        </svg>
      </div>

      <div className={styles.pkgTitle}>
        <h4>AI 추천 패키지</h4>
        <span className={styles.badge}>일정 맞춤</span>
      </div>

      {PACKAGES.map((p) => (
        <div className={styles.pkgRow} key={p.title}>
          <div className={styles.pkgThumb}>{p.icon}</div>
          <div className={styles.pkgInfo}>
            <div className={styles.rating}>{p.rating}</div>
            <h5>{p.title}</h5>
            <div className={styles.price}>{p.price}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
