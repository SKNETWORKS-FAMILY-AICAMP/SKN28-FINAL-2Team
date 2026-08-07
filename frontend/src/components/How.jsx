const STEPS = [
  { num: 1, title: '조건 입력', desc: '기간·인원·여행 스타일을\n대화로 알려줘요', active: true },
  { num: 2, title: '일정 생성·수정', desc: '맞춤 여행 일정을\n자동으로 만들어요' },
  { num: 3, title: '최종 일정 확인', desc: '일정을 확인하고\n총 비용을 살펴봐요' },
  { num: 4, title: '예약 및 저장', desc: '추천 패키지를 예약하고\nPDF로 저장해요' },
  { num: 5, title: '완료', desc: '여행 준비를 마치고\n즐거운 여행을 떠나요' },
]

export default function How() {
  return (
    <section className="how" id="how">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">진행 순서</div>
          <h2 className="section-title">
            🍊 제주 여행
            <br />
           &nbsp; &nbsp; &nbsp;다섯 걸음이면 충분해요
          </h2>
          <p className="section-sub">
            여행 조건을 알려주면 AI가 일정을 만들고, 확인부터 패키지 예약까지 차근차근 함께해요.
          </p>
        </div>
        <div className="flow">
          {STEPS.map((step) => (
            <div key={step.num} className={`flow-step reveal${step.active ? ' active' : ''}`}>
              <div className="flow-num">{step.num}</div>
              <h4>{step.title}</h4>
              <p>
                {step.desc.split('\n').map((line, i) => (
                  <span key={i}>
                    {line}
                    {i < step.desc.split('\n').length - 1 && <br />}
                  </span>
                ))}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}