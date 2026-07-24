const FEATURES = [
  {
    icon: '💬',
    title: '대화로 바로 수정',
    desc: '"카페를 하나 더 넣어줘", "오후 일정을 줄여줘"처럼 말하면 일정이 즉시 다시 짜여요.',
  },
  {
    icon: '🗺️',
    title: '지도로 동선 확인',
    desc: '하루 동선이 지도에 그대로 표시돼서, 이동 거리와 순서를 한눈에 볼 수 있어요.',
  },
  {
    icon: '🏝️',
    title: '숙소·렌터카 한 번에',
    desc: '완성된 일정에 맞춰 숙소와 렌터카 패키지를 추천받고, 예약과 결제까지 이어져요.',
  },
]

export default function Features() {
  return (
    <section className="features">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">할 수 있는 것들</div>
          <h2 className="section-title">
            일정 짜기부터 예약까지,
            <br />한 화면에서 끝나요
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
