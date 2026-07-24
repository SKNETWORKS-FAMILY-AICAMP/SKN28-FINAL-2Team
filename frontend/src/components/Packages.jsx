const PACKAGES = [
  { icon: '🏨', rating: '★ 4.8 (321)', title: '해비치 호텔 & 리조트 제주', price: '159,000원 ~' },
  { icon: '🚗', rating: '★ 4.7 (532)', title: '제주 올레 렌터카 3일', price: '89,700원 ~' },
  { icon: '🌊', rating: '★ 4.6 (218)', title: '제주 카약 체험 2인', price: '70,000원 ~' },
]

export default function Packages() {
  return (
    <section className="packages" id="packages">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">AI 추천 패키지</div>
          <h2 className="section-title">
            일정에 딱 맞는
            <br />
            숙소·렌터카를 골라드려요
          </h2>
        </div>
        <div className="pkg-grid">
          {PACKAGES.map((p) => (
            <div className="pkg reveal" key={p.title}>
              <div className="pkg-img">{p.icon}</div>
              <div className="pkg-body">
                <div className="rating">{p.rating}</div>
                <h4>{p.title}</h4>
                <div className="price">{p.price}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
