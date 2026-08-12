const FEATURES = [
  {
    icon: '💬',
    title: 'AI 맞춤 일정',
    desc: '여행 기간과 취향만 입력하면 AI가 나만의 제주 여행 일정을 만들어드립니다.',
  },
  {
    icon: '🗺️',
    title: '일정 관리',
    desc: '대화로 일정을 수정하고, 지도에서 이동 동선을 확인하며 원하는 여행으로 완성할 수 있어요.',
  },
  {
    icon: '🎁',
    title: '맞춤 패키지 & 공유',
    desc: '완성된 일정과 가장 잘 맞는 탐나플랜 패키지를 추천받고, PDF 저장이나 공유도 가능해요.',
  },
]

export default function Features() {
  return (
    <section className="features">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">할 수 있는 것들</div>
          <h2 className="section-title">
            나만의 일정부터 패키지 예약까지,
            <br />한 곳에서 완성하세요
          </h2>
        </div>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <div className="feature reveal" key={f.title}>
              <div className="f-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}