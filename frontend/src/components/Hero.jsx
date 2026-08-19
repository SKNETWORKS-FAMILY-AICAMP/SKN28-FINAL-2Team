import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'

export default function Hero() {
  const navigate = useNavigate()
  const [activeStep, setActiveStep] = useState(1)

  const handleStart = () => {
    const token = localStorage.getItem('accessToken')

    if (!token || token === 'null' || token === 'undefined') {
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
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="dot"></span>
            AI 맞춤 제주 여행 🍊
          </div>

          <h1>
            채팅으로 만든 내 일정,
            <br />
            그대로 <span className="accent">예약</span> 할 수 있어요
          </h1>

          <p className="lede">
            여행 조건과 취향만 알려주면
            <br />
            AI가 나만의 제주 일정을 만들어요.
            <br />
            완성한 일정은 그대로 예약 가능한 패키지가 되고,
            <br />
            비슷한 여행사 패키지와 가격까지 비교해
            <br />
            더 좋은 쪽으로 예약할 수 있어요.
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

        <div className="hero-service">
          <div className="service-mockup">

            <div className="service-steps">
              <button
                type="button"
                className={`service-step ${activeStep === 1 ? 'active' : ''}`}
                onClick={() => setActiveStep(1)}
              >
                <span>1</span>
                대화로 일정 만들기
              </button>

              <button
                type="button"
                className={`service-step ${activeStep === 2 ? 'active' : ''}`}
                onClick={() => setActiveStep(2)}
              >
                <span>2</span>
                두 상품 비교하기
              </button>

              <button
                type="button"
                className={`service-step ${activeStep === 3 ? 'active' : ''}`}
                onClick={() => setActiveStep(3)}
              >
                <span>3</span>
                선택하고 예약하기
              </button>
            </div>

            {activeStep === 1 && (
              <div className="service-content">

                <div className="service-chat">
                  <div className="service-chat-header">
                    <div className="service-chat-avatar">🍊</div>

                    <div>
                      <strong>AI 여행 코치</strong>
                      <span>대화 중</span>
                    </div>

                    <span className="service-more">•••</span>
                  </div>

                  <div className="service-chat-body">
                    <div className="service-bubble bot">
                      누구와 언제 제주로 떠나시나요?
                    </div>

                    <div className="service-bubble user">
                      부모님과 2박 3일로 갈 거예요
                    </div>

                    <div className="service-bubble bot">
                      어떤 여행을 원하시나요?
                    </div>

                    <div className="service-bubble user">
                      많이 걷지 않고 동부 바다와 숲을 보고 싶어요
                    </div>

                    <div className="service-bubble bot">
                      부모님과 편하게 즐기는 동부 일정을
                      만들어드릴게요.
                      <br />
                      마음에 들지 않는 장소는 대화로 바꿀 수 있어요!
                    </div>

                    <div className="service-quick-actions">
                      <span>관광지 추가</span>
                      <span>맛집 추가</span>
                      <span>동선 변경</span>
                    </div>
                  </div>

                  <div className="service-chat-input">
                    <span>메시지를 입력하세요...</span>
                    <button type="button">➤</button>
                  </div>
                </div>

                <div className="service-itinerary">
                  <div className="service-preview-head">
                    <div>
                      <span>일정 미리보기</span>
                      <h3>부모님과 제주 동부 2박 3일</h3>
                    </div>

                    <span className="edit-badge">수정 가능</span>
                  </div>

                  <div className="itinerary-days">
                    <div className="itinerary-day">
                      <strong>DAY 1</strong>

                      <div className="place-grid">
                        <div>
                          <span>1</span>
                          성산일출봉
                        </div>

                        <div>
                          <span>2</span>
                          섭지코지
                        </div>

                        <div>
                          <span>3</span>
                          성산 흑돼지 식당
                        </div>

                        <div>
                          <span>4</span>
                          아쿠아플라넷 제주
                        </div>
                      </div>
                    </div>

                    <div className="itinerary-day">
                      <strong>DAY 2</strong>

                      <div className="place-grid">
                        <div>
                          <span>1</span>
                          비자림
                        </div>

                        <div>
                          <span>2</span>
                          구좌 해산물 식당
                        </div>

                        <div>
                          <span>3</span>
                          스누피가든
                        </div>

                        <div>
                          <span>4</span>
                          함덕해수욕장
                        </div>
                      </div>
                    </div>

                    <div className="itinerary-day">
                      <strong>DAY 3</strong>

                      <div className="place-grid">
                        <div>
                          <span>1</span>
                          도두봉
                        </div>

                        <div>
                          <span>2</span>
                          제주 향토 음식점
                        </div>

                        <div>
                          <span>3</span>
                          이호테우해변
                        </div>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="itinerary-confirm"
                    onClick={() => setActiveStep(2)}
                  >
                    이 일정으로 확정하기 →
                  </button>
                </div>
              </div>
            )}

            {activeStep === 2 && (
              <div className="package-compare">
                <div className="compare-heading">

                  <h3>내 일정과 가장 잘 맞는 패키지를 비교해보세요</h3>
                  <p>
                    내가 만든 자유일정도 하나의 패키지로 예약할 수 있어요.
                  </p>
                </div>

                <div className="compare-cards">

                  <div className="compare-card mine">
                    <div className="compare-label">
                      내가 만든 자유일정
                    </div>

                    <h4>부모님과 제주 동부 2박 3일</h4>

                    <div className="compare-price">
                      258,000<span>원 / 1인</span>
                    </div>

                    <div className="compare-list">
                      <div>✓ 직접 수정한 일정</div>
                      <div>✓ 원하는 장소 반영 </div>
                      <div>✓ 숙소 · 식사 포함</div>
                    </div>

                    <div className="compare-preview">
                      <span className="compare-preview-label">주요 일정 미리보기</span>
                      <div className="compare-preview-days">
                        <div><b>DAY 1</b><span>성산일출봉 · 섭지코지 · 흑돼지</span></div>
                        <div><b>DAY 2</b><span>비자림 · 구좌 해산물 · 스누피가든</span></div>
                        <div><b>DAY 3</b><span>도두봉 · 제주 향토 음식점</span></div>
                      </div>
                    </div>

                  </div>

                  <div className="compare-vs">
                    VS
                  </div>

                  <div className="compare-card recommended">
                    <div className="compare-label">
                      BEST MATCH
                    </div>

                    <h4>아이와 가족 서부 1박 2일</h4>

                    <div className="compare-price">
                      230,000<span>원 / 1인</span>
                    </div>

                    <div className="compare-list">
                      <div>✓ 비슷한 여행 동선</div>
                      <div>✓ 숙소 · 식사 포함</div>
                      <div>✓ 바로 예약 가능</div>
                    </div>

                    <div className="compare-preview">
                      <span className="compare-preview-label">일정 미리보기</span>
                      <div className="compare-preview-days">
                        <div><b>DAY 1</b><span>협재해수욕장 · 오설록 · 산방산</span></div>
                        <div><b>DAY 2</b><span>용눈이오름 · 천제연폭포 · 서귀포매일올레시장</span></div>
                      </div>
                    </div>

                  </div>

                </div>

                <button
                  type="button"
                  className="itinerary-confirm"
                  onClick={() => setActiveStep(3)}
                >
                  두 상품 비교하고 선택하기 →
                </button>
              </div>
            )}

            {activeStep === 3 && (
              <div className="booking-preview">

                <div className="booking-heading">
                  <span>패키지 선택</span>
                  <h3>마음에 드는 여행을 선택하고 예약하세요</h3>
                </div>

                <div className="booking-options">

                  <div className="booking-option">
                    <div>
                      <small>내가 만든 자유일정</small>
                      <strong>부모님과 제주 동부 2박 3일</strong>
                      <b>258,000원 / 1인</b>
                    </div>

                    <button type="button">
                      선택하기
                    </button>
                  </div>

                  <div className="booking-option best">
                    <div>
                      <div className="booking-option-label">
                        <small>BEST MATCH 추천 패키지</small>
                        <span>내 일정과 92% 유사해요!</span>
                      </div>
                      <strong>아이와 가족 서부 1박 2일</strong>
                      <b>230,000원 / 1인</b>
                    </div>

                    <button type="button">
                      선택하기
                    </button>
                  </div>

                  </div>

                  <div className="booking-message">
                    🍊 선택한 패키지의 상세 일정, 포함 내역, 숙소 정보를 확인할 수 있어요.
                  </div>

                <button
                  type="button"
                  className="itinerary-confirm"
                  onClick={handleStart}
                >
                  예약하러 가기 →
                </button>
              </div>
            )}

          </div>
        </div>
      </div>
    </section>
  )
}