import { useState } from 'react'
import harubangAvatar from '../assets/harubang-avatar.png'

const TRIP_DAYS = [
  { day: 1, places: ['성산일출봉', '섭지코지', '성산 흑돼지 식당', '아쿠아플라넷 제주'] },
  { day: 2, places: ['비자림', '구좌 해산물 식당', '스누피가든', '함덕해수욕장'] },
  { day: 3, places: ['도두봉', '제주 향토 음식점', '이호테우해변'] },
]

const DEMO_STEPS = [
  { id: 'chat', num: 1, label: '대화로 일정 만들기' },
  { id: 'compare', num: 2, label: '두 상품 비교하기' },
  { id: 'booking', num: 3, label: '선택하고 예약하기' },
]

function MiniSchedule({ compact = false }) {
  return (
    <div className={`usage-schedule${compact ? ' compact' : ''}`}>
      {TRIP_DAYS.map((day) => (
        <div className="usage-day" key={day.day}>
          <strong>DAY {day.day}</strong>
          <div className="usage-place-list">
            {day.places.map((place, index) => (
              <span key={place}>
                <b>{index + 1}</b>
                {place}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function ChatDemo() {
  return (
    <div className="usage-chat-grid">
      <div className="usage-chat-panel">
        <div className="usage-panel-head">
          <span className="usage-avatar"><img src={harubangAvatar} alt="탐나플랜 하르방" /></span>
          <div><strong>AI 여행 코치</strong><small>대화 중</small></div>
        </div>
        <div className="usage-messages">
          <p className="usage-ai-message">누구와 언제 제주로 떠나시나요?</p>
          <p className="usage-user-message">부모님과 2박 3일로 갈 거야</p>
          <p className="usage-ai-message">어떤 여행을 원하시나요?</p>
          <p className="usage-user-message">많이 걷지 않고 동부 바다와 숲을 보고 싶어</p>
          <p className="usage-ai-message">부모님과 편하게 즐기는 동부 일정을 만들었어요. 마음에 들지 않는 장소는 대화로 바꿀 수 있어요!</p>
        </div>
        <div className="usage-quick-actions">
          <span>관광지 추가</span><span>맛집 추가</span><span>동선 변경</span>
        </div>
      </div>

      <div className="usage-preview-panel">
        <div className="usage-preview-title">
          <div><span>일정 미리보기</span><h3>부모님과 제주 동부 2박 3일</h3></div>
          <em>수정 가능</em>
        </div>
        <MiniSchedule compact />
        <button type="button" className="usage-primary-button">이 일정으로 확정하기 →</button>
      </div>
    </div>
  )
}

function CompareDemo() {
  return (
    <div className="usage-compare-wrap">
      <div className="usage-map-preview">
        <div><span>1일차</span><span>2일차</span><span>3일차</span></div>
        <strong>두 일정의 이동 동선을 지도에서 비교</strong>
        <p>추천 패키지와 자유일정을 선택해 각각의 경로를 확인해요.</p>
      </div>
      <div className="usage-product-grid">
        <article className="usage-product-card recommended">
          <div className="usage-ribbon">BEST MATCH</div>
          <div className="usage-product-head">
            <div><span>우리 여행사 추천 패키지</span><h3>가족과 함께하는 제주 동부 2박 3일</h3></div>
            <strong>480,000원<small> / 1인</small></strong>
          </div>
          <p>확정 일정과 관광지·동행 조건이 가장 유사한 패키지예요.</p>
          <div className="usage-route-summary">성산일출봉 · 섭지코지 · 비자림 · 함덕해수욕장 외</div>
          <div className="usage-benefits"><span>✓ 숙소 포함</span><span>✓ 바로 예약 가능</span></div>
          <button type="button">추천 패키지 선택</button>
        </article>

        <article className="usage-product-card custom">
          <div className="usage-product-head">
            <div><span>내가 만든 자유일정</span><h3>확정한 일정 그대로 예약</h3></div>
            <strong>538,000원<small> / 1인</small></strong>
          </div>
          <p>대화로 완성한 관광지와 맛집 일정을 그대로 이용하는 상품이에요.</p>
          <div className="usage-route-summary">내가 확정한 2박 3일 관광지·맛집 일정 포함</div>
          <div className="usage-benefits"><span>✓ 일정 맞춤 구성</span><span>✓ 숙소 미포함</span></div>
          <button type="button">자유일정 선택</button>
        </article>
      </div>
    </div>
  )
}

function BookingDemo() {
  return (
    <div className="usage-booking-grid">
      <div className="usage-booking-product">
        <span className="usage-booking-label">선택한 상품</span>
        <div className="usage-selected-product">
          <span className="usage-check">✓</span>
          <div><strong>가족과 함께하는 제주 동부 2박 3일</strong><p>여행사 패키지 · 숙소 포함 · 1인 기준</p></div>
          <b>480,000원</b>
        </div>
        <div className="usage-booking-note">장바구니에 담아 두 상품을 함께 확인하거나, 선택한 상품을 바로 예약할 수 있어요.</div>
      </div>
      <aside className="usage-payment-card">
        <span>결제 정보</span>
        <p>총 결제 금액</p>
        <strong>480,000원</strong>
        <div><span>상품 금액</span><b>480,000원</b></div>
        <div><span>할인 쿠폰</span><b>-0원</b></div>
        <hr />
        <div><span>총 합계</span><b>480,000원</b></div>
        <button type="button">예약 및 결제하기 →</button>
      </aside>
    </div>
  )
}

export default function Itinerary() {
  const [activeDemo, setActiveDemo] = useState('chat')

  return (
    <section className="itinerary" id="itinerary">
      <div className="wrap">
        <div className="itinerary-head reveal">
          <div>
            <div className="section-tag">실제 이용 예시</div>
            <h2 className="section-title">
              대화로 만든 일정부터
              <br />상품 비교와 예약까지
            </h2>
            <p className="section-sub">각 단계를 눌러 탐나플랜의 새로운 이용 흐름을 확인해보세요.</p>
          </div>
        </div>

        <div className="usage-demo reveal">
          <div className="usage-demo-tabs">
            {DEMO_STEPS.map((step) => (
              <button
                type="button"
                key={step.id}
                className={activeDemo === step.id ? 'active' : ''}
                onClick={() => setActiveDemo(step.id)}
              >
                <b>{step.num}</b>{step.label}
              </button>
            ))}
          </div>

          <div className="usage-demo-stage">
            {activeDemo === 'chat' && <ChatDemo />}
            {activeDemo === 'compare' && <CompareDemo />}
            {activeDemo === 'booking' && <BookingDemo />}
          </div>
        </div>
      </div>
    </section>
  )
}