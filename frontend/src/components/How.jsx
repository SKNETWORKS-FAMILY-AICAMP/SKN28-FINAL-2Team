const STEPS = [
  { num: 1, title: '조건 입력', desc: '기간·인원·예산을\n대화로 알려줘요', active: true },
  { num: 2, title: '일정 생성·수정', desc: '동선까지 짜인 일정을\n말로 바로 고쳐요' },
  { num: 3, title: '최종 일정 확인', desc: '하루씩 펼쳐보고\n총 비용을 확인해요' },
  { num: 4, title: '예약 및 저장', desc: '숙소·렌터카를 골라\n한 번에 결제해요' },
  { num: 5, title: '완료', desc: '예약 번호를 받고\n여행을 떠나요' },
]

export default function How() {
  return (
    <section className="how" id="how">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">진행 순서</div>
          <h2 className="section-title">
            대화 한 번으로
            <br />
            예약까지 끝나는 다섯 단계
          </h2>
          <p className="section-sub">
            조건을 말하고, 일정을 다듬고, 확인하고, 예약까지 — 앱 하나에서 순서대로 이어져요.
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
