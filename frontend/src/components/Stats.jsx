const STATS = [
  { n: '28만+', l: '완성된 여행 일정' },
  { n: '4.8 / 5', l: '이용자 평균 만족도' },
  { n: '318개', l: '등록된 숙소·투어 패키지' },
  { n: '47초', l: '평균 첫 일정 생성 시간' },
]

export default function Stats() {
  return (
    <section className="stats">
      <div className="wrap">
        {STATS.map((s) => (
          <div className="stat" key={s.l}>
            <div className="n">{s.n}</div>
            <div className="l">{s.l}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
