import { Link } from 'react-router-dom'

export default function FinalCTA() {
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
        <Link to="/chat" className="btn primary">
          무료로 일정 만들기 →
        </Link>
      </div>
    </section>
  )
}
