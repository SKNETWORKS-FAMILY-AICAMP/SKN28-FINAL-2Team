import { Link } from 'react-router-dom'
import styles from './account.module.css'
import cx from '../../utils/cx.js'

const TABS = [
  { to: '/mypage', label: '👤 마이페이지' },
  { to: '/my/itineraries', label: '🗓️ 내 일정' },
  { to: '/my/bookmarks', label: '❤️ 찜한 패키지' },
  { to: '/my/reservations', label: '🧾 예약 내역' },
]

export default function AccountTabs({ active }) {
  return (
    <div className={styles.tabs}>
      {TABS.map((tab) => (
        <Link key={tab.to} to={tab.to} className={cx(styles.tab, active === tab.to && styles.tabActive)}>
          {tab.label}
        </Link>
      ))}
    </div>
  )
}
