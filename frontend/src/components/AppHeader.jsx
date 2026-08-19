import { Link } from 'react-router-dom'

import AccountMenu from './AccountMenu.jsx'

const defaultStyles = {
  appnav: 'nav nav-inner',
  logo: 'logo',
  logoMark: 'logo-mark',
  appLinks: 'nav-links',
  appRight: 'nav-right',
}

export default function AppHeader({ styles }) {
  styles = styles || defaultStyles

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
        <Link to="/my/itineraries">내 일정</Link>
        <Link to="/my/bookmarks">찜한 패키지</Link>
      </nav>
      <div className={styles.appRight}>
        <AccountMenu />
      </div>
    </header>
  )
}
