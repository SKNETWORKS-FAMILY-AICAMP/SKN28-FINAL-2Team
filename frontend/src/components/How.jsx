import harubangSunglasses from '../assets/harubang-sunglasses.png'

const STEPS = [
  { num: 1, title: '여행 조건 대화', desc: '동행·날짜와 원하는 여행을\n자연스럽게 이야기해요', active: true },
  { num: 2, title: 'AI 일정 생성·수정', desc: 'AI가 만든 일정을 보고\n대화로 자유롭게 수정해요' },
  { num: 3, title: '일정 확정', desc: '마음에 드는 일정을\n최종 일정으로 확정해요' },
  { num: 4, title: '두 상품 비교', desc: '추천 패키지와 자유일정의\n코스와 가격을 비교해요' },
  { num: 5, title: '선택 및 예약', desc: '원하는 상품을 선택해\n장바구니에 담거나 예약해요' },
]

export default function How() {
  return (
    <section className="how" id="how">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">진행 순서</div>
          <h2 className="section-title">
            <span className="how-title-with-mascot">
              <img src={harubangSunglasses} alt="선글라스를 쓴 탐나플랜 하르방" />
              제주 여행
            </span>
            <br />
           &nbsp; &nbsp; &nbsp;다섯 걸음이면 충분해요
          </h2>
          <p className="section-sub">
            AI와 대화하며 일정을 완성한 뒤, 비슷한 여행사 패키지와 자유일정을 비교하고 예약할 수 있어요.
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
