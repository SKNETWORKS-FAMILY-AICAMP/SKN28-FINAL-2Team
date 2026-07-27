import { Link } from 'react-router-dom'
import styles from './booking.module.css'

export default function AppHeader() {
  return (
    <header className={styles.appnav}>
      <Link to="/" className={styles.logo}>
        <span className={styles.logoMark}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
            <path d="M12 2c4 3 6 7 6 11a6 6 0 0 1-12 0c0-4 2-8 6-11z" fill="#fff" />
          </svg>
        </span>
        탐나플랜
      </Link>
      <nav className={styles.appLinks}>
        <a href="#">내 여행</a>
        <a href="#">저장한 일정</a>
      </nav>
      <div className={styles.appRight}>
        <div className={styles.avatar}>🙂</div>
      </div>
    </header>
  )
}
