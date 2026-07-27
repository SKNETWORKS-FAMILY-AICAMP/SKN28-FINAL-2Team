import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import styles from './AccountMenu.module.css'

export default function AccountMenu() {
  const { user, isLoggedIn, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  if (!isLoggedIn) {
    return (
      <Link to="/login" className={styles.loginBtn}>
        로그인
      </Link>
    )
  }

  const handleLogout = () => {
    logout()
    setOpen(false)
    navigate('/')
  }

  return (
    <div className={styles.wrap}>
      <button className={styles.avatarBtn} onClick={() => setOpen((v) => !v)} aria-label="계정 메뉴">
        {user.profileImage ? <img src={user.profileImage} alt="" /> : '🙂'}
      </button>

      {open && (
        <>
          <div className={styles.backdrop} onClick={() => setOpen(false)}></div>
          <div className={styles.dropdown}>
            <div className={styles.dropdownName}>
              {user.nickname}
              <div className={styles.dropdownEmail}>{user.email}</div>
            </div>
            <Link to="/mypage" onClick={() => setOpen(false)}>
              👤 마이페이지
            </Link>
            <Link to="/my/itineraries" onClick={() => setOpen(false)}>
              🗓️ 내 일정
            </Link>
            <Link to="/my/bookmarks" onClick={() => setOpen(false)}>
              ❤️ 찜한 패키지
            </Link>
            <Link to="/my/reservations" onClick={() => setOpen(false)}>
              🧾 예약 내역
            </Link>
            <button className={styles.logoutBtn} onClick={handleLogout}>
              🚪 로그아웃
            </button>
          </div>
        </>
      )}
    </div>
  )
}
