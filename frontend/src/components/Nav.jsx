import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import AccountMenu from './AccountMenu.jsx'

export default function Nav() {
  const navigate = useNavigate()
  const { isLoggedIn } = useAuth()

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
    <header className="nav">
      <div className="nav-inner">
        <Link to="/" className="logo">
          <span className="logo-mark">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 2c4 3 6 7 6 11a6 6 0 0 1-12 0c0-4 2-8 6-11z"
                fill="#fff"
              />
            </svg>
          </span>
          탐나플랜
        </Link>

        <nav className="nav-links">
          <Link to="/how-to-use">이용 방법</Link>
          <Link to="/packages">추천 패키지</Link>
        </nav>

        <div className="nav-right">
          <AccountMenu />
          <button
            type="button"
            className="btn primary sm"
            onClick={handleStart}
          >
            무료로 일정 만들기
          </button>
        </div>
      </div>
    </header>
  )
}