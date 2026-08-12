import { Link, useNavigate } from 'react-router-dom'

export default function Hero() {
  const navigate = useNavigate()

  const handleStart = () => {
    const token = localStorage.getItem('accessToken')

    if (
      !token ||
      token === 'null' ||
      token === 'undefined'
    ) {
      alert('로그인 후 이용할 수 있습니다.')
      return
    }

    sessionStorage.removeItem('travel-chat-page')
    sessionStorage.removeItem('travel-chat-column')

    navigate('/chat')
  }

  return (
    <section className="hero">
      <div className="wrap hero-grid">
        <div>
          <div className="eyebrow">
            <span className="dot"></span>AI 맞춤 제주 여행
          </div>
          <h1>
            "부모님과 힐링 여행"
            <br />한 마디면
            <br />
            <span className="accent">일정이 완성</span>돼요
          </h1>
          <p className="lede">
            여행 기간과 취향만 알려주세요. AI가 나만의 제주 여행 일정을 만들고, 일정과 가장 잘 맞는 탐라플랜 패키지를 추천해드려요. 
            원하는 일정은 예약하거나 PDF 저장 및 공유도 가능해요.
          </p>
          <div className="hero-ctas">
            <button
              type="button"
              className="btn primary"
              id="start"
              onClick={handleStart}
            >
              무료로 일정 만들기 →
            </button>
            <Link to="/how-to-use" className="btn ghost">
              이용 방법 보기
            </Link>
          </div>
        </div>

        <div className="mockup-wrap">
          <svg className="mascot m1" viewBox="0 0 200 220" fill="none">
            <ellipse cx="100" cy="205" rx="50" ry="9" fill="#1B211D" opacity="0.08" />
            <g className="dolharubang">
              <path
                d="M55 120c0-45 20-80 45-80s45 35 45 80c0 15-8 25-45 25s-45-10-45-25z"
                fill="#F5E6C8"
                stroke="#1B211D"
                strokeWidth="3"
              />
              <circle cx="80" cy="105" r="5" fill="#1B211D" />
              <circle cx="120" cy="105" r="5" fill="#1B211D" />
              <path d="M85 122c5 5 25 5 30 0" stroke="#1B211D" strokeWidth="3" strokeLinecap="round" />
              <path
                d="M63 92c5-14 15-22 37-22s32 8 37 22"
                stroke="#1B211D"
                strokeWidth="3"
                fill="none"
                strokeLinecap="round"
              />
              <rect x="70" y="140" width="60" height="55" rx="18" fill="#2E9E62" stroke="#1B211D" strokeWidth="3" />
              <circle cx="100" cy="160" r="7" fill="#C7E263" stroke="#1B211D" strokeWidth="2.5" />
              <g className="hand">
                <path d="M130 150c15-5 25 2 28 14" stroke="#1B211D" strokeWidth="6" strokeLinecap="round" />
                <circle cx="160" cy="158" r="9" fill="#F5E6C8" stroke="#1B211D" strokeWidth="3" />
              </g>
            </g>
          </svg>
          <span className="sticker s1">일정 완성! 🍊</span>
          <div className="mockup">
            <div className="mockup-bar">
              <span></span>
              <span></span>
              <span></span>
              <div className="mockup-title">AI 대화 코치</div>
            </div>
            <div className="mockup-body">
              <div className="chat-line me">
                <div className="who">나</div>
                <div className="chat-bubble">우도 대신 협재해변으로 바꿔주세요</div>
              </div>

              <div className="chat-line">
                <div className="who">🍊</div>
                <div className="chat-bubble">
                  알겠습니다! 우도를 협재해변으로 바꿨어요. 이동 시간도 20분 줄었어요.
                </div>
              </div>

              <div style={{ height: '1px', background: 'var(--line)', margin: '16px 0' }}></div>

              <div className="mini-card">
                <div className="mini-time">09:30</div>
                <div className="mini-dot-col">
                  <div className="mini-dot"></div>
                  <div className="mini-line"></div>
                </div>
                <div className="mini-body">
                  <h5>성산일출봉</h5>
                  <p>대표 관광지 · 1시간 30분</p>
                </div>
              </div>
              <div className="mini-card">
                <div className="mini-time">12:00</div>
                <div className="mini-dot-col">
                  <div className="mini-dot"></div>
                  <div className="mini-line"></div>
                </div>
                <div className="mini-body">
                  <h5>협재해변</h5>
                  <p>에메랄드빛 바다 · 1시간 30분</p>
                </div>
              </div>
              <div className="mini-card">
                <div className="mini-time">15:30</div>
                <div className="mini-dot-col">
                  <div className="mini-dot"></div>
                </div>
                <div className="mini-body">
                  <h5>오설록 티뮤지엄</h5>
                  <p>녹차밭 산책 · 1시간 30분</p>
                </div>
              </div>

              <div className="mockup-cta">
                <div>
                  <div className="lbl">제주 2박 3일 힐링 여행</div>
                </div>
                <button className="btn primary sm">일정 확정하기</button>
              </div>
            </div>
          </div>
          <span className="sticker s2">협재해변 💙</span>
        </div>
      </div>
      <svg className="wavy" viewBox="0 0 1440 44" preserveAspectRatio="none">
        <path
          d="M0,22 C240,44 480,0 720,22 C960,44 1200,0 1440,22 L1440,44 L0,44 Z"
          style={{ fill: '#E7F5EC' }}
        />
      </svg>
    </section>
  )
}