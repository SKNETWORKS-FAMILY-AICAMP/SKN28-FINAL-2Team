import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function FinalCTA() {
  const navigate = useNavigate()
  const { isLoggedIn } = useAuth()

  const handleStart = () => {
    if (!isLoggedIn) {
      alert('로그인 후 이용할 수 있습니다.')
      return
    }

    navigate('/chat')
  }
  return (
    <section className="final-cta">
      <div className="wrap reveal">
        <div className="final-badge">✓</div>
        <h2>
          다음 제주 여행,
          <br />
          이번엔 대화로 짜보세요
        </h2>
        <p>
          검색창에 일정을 끼워 맞추는 대신, 원하는 대로 말하기만 하면 됩니다. 지금 시작하면 1분
          안에 첫 일정을 받아볼 수 있어요.
        </p>
        <button
          type="button"
          className="btn primary"
          onClick={handleStart}
        >
          무료로 일정 만들기 →
        </button>
      </div>
    </section>
  )
}
