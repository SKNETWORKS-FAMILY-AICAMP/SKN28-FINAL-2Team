import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import AccountMenu from './AccountMenu.jsx'
import tamnplanLogo from '../assets/tamnplan_logo.png'
import styles from './AppHeader.module.css'

export default function AppHeader({ variant = 'app' }) {
  const navigate = useNavigate()
  const { isLoggedIn } = useAuth()
  const isMain = variant === 'main'

  const handleStart = () => {
    if (!isLoggedIn) {
      alert('로그인 후 이용할 수 있습니다.')
      return
    }

    sessionStorage.removeItem('travel-chat-page')
    sessionStorage.removeItem('travel-chat-column')
    navigate('/chat')
  }

  return (
    <header className={styles.nav}>
      <div className={styles.navInner}>
        <Link to="/" className={styles.logo}>
          <img src={tamnplanLogo} alt="탐나플랜" className={styles.logoImage} />
        </Link>

        <nav className={styles.navLinks}>
          {isMain ? (
            <>
              <Link to="/how-to-use">이용 방법</Link>
              <Link to="/packages">추천 패키지</Link>
            </>
          ) : (
            <>
              <Link to="/my/itineraries">내 일정</Link>
              <Link to="/my/bookmarks">찜한 패키지</Link>
            </>
          )}
        </nav>

        <div className={styles.navRight}>
          <AccountMenu />
          {isMain && (
            <button
              type="button"
              className={`${styles.btn} ${styles.primary} ${styles.sm}`}
              onClick={handleStart}
            >
              무료로 일정 만들기
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
