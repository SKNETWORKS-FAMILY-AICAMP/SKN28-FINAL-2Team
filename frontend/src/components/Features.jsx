import harubangMap from '../assets/harubang-map.png'
import harubangHello from '../assets/harubang-hello.png'
import harubangTraveler from '../assets/harubang-traveler.png'

const FEATURES = [
  {
    icon: harubangMap,
    iconAlt: '지도를 보는 하르방',
    title: 'AI와 만드는 맞춤 일정',
    desc: '동행과 날짜, 원하는 여행을 자연스럽게 말하면 AI가 제주 여행 일정을 만들어드려요.',
  },
  {
    icon: harubangHello,
    iconAlt: '인사하는 하르방',
    title: '대화로 자유롭게 수정',
    desc: '관광지와 맛집을 대화로 추가하거나 바꾸고, 지도에서 이동 동선도 확인할 수 있어요.',
  },
  {
    icon: harubangTraveler,
    iconAlt: '여행자 하르방',
    title: '두 상품 비교·예약',
    desc: '확정한 자유일정과 가장 비슷한 여행사 패키지를 코스와 가격으로 비교해 선택할 수 있어요.',
  },
]

export default function Features() {
  return (
    <section className="features">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">할 수 있는 것들</div>
          <h2 className="section-title">
            대화형 일정부터 상품 비교·예약까지,
            <br />한 곳에서 완성하세요
          </h2>
        </div>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <div className="feature reveal" key={f.title}>
              <div className="f-icon">
                <img src={f.icon} alt={f.iconAlt} />
              </div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}