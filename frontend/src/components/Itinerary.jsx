import { useState } from 'react'

const DAYS = [
  {
    dayNumber: 1,
    date: '7/25 (목)',
    items: [
      { time: '09:30', title: '성산일출봉', description: '일출 명소로 유명한 제주 동쪽의 대표 관광지', dur: '체류 1시간 30분' },
      { time: '12:00', title: '협재해변', description: '에메랄드빛 바다와 하얀 모래 백사장', dur: '체류 1시간 30분' },
      { time: '13:30', title: '점심 식사', description: '현지 맛집에서 제주 흑돼지 정식', dur: '체류 1시간' },
      { time: '15:30', title: '오설록 티뮤지엄', description: '녹차밭과 티하우스를 함께 즐길 수 있는 공간', dur: '체류 1시간 30분' },
      { time: '17:30', title: '숙소 체크인', description: '편안한 휴식을 위한 협재 인근 숙소', dur: '' },
    ],
  },
  {
    dayNumber: 2,
    date: '7/26 (금)',
    items: [
      { time: '09:00', title: '사려니숲길', description: '편백나무 향 가득한 산책로, 부모님 걸음에 맞춰 여유롭게', dur: '체류 1시간' },
      { time: '11:00', title: '동문관덕정', description: '제주 전통 시장 골목 구경', dur: '체류 1시간' },
      { time: '12:30', title: '점심 식사 — 흑돼지 맛집', description: '현지인 추천 흑돼지 맛집', dur: '체류 1시간' },
      { time: '14:30', title: '카페 스누피가든', description: '사진 찍기 좋은 테마 카페 겸 정원', dur: '체류 1시간 30분' },
      { time: '19:00', title: '저녁 식사 — 물회국수', description: '제주식 시원한 물회 한 그릇', dur: '' },
    ],
  },
  {
    dayNumber: 3,
    date: '7/27 (토)',
    items: [
      { time: '09:00', title: '협재 해변 산책', description: '마지막 날 아침 여유로운 바다 산책', dur: '체류 1시간' },
      { time: '11:00', title: '점심 식사 — 해물뚝배기', description: '떠나기 전 든든한 한 끼', dur: '체류 1시간' },
      { time: '13:00', title: '아르떼뮤지엄', description: '몰입형 미디어아트 전시로 마무리', dur: '체류 1시간 30분' },
      { time: '16:00', title: '공항 이동 및 출국', description: '렌터카 반납 후 공항으로 이동', dur: '' },
    ],
  },
]

export default function Itinerary() {
  const [activeDay, setActiveDay] = useState(1)
  const current = DAYS.find((d) => d.dayNumber === activeDay)

  return (
    <section className="itinerary" id="itinerary">
      <div className="wrap">
        <div className="itinerary-head reveal">
          <div>
            <div className="section-tag">일정 예시</div>
            <h2 className="section-title">
              제주 2박 3일 힐링 여행
              <br />— 부모님과 함께
            </h2>
          </div>
        </div>

        <div className="it-shell reveal">
          <div className="it-side">
            <div className="summary">
              <h4>제주 2박 3일 힐링 여행</h4>
              <p>
                부모님과 함께
                <br />
                2박 3일 · 2명 · 1인당 50만원
              </p>
            </div>
            {DAYS.map((d) => (
              <button
                key={d.dayNumber}
                className={`day-tab${activeDay === d.dayNumber ? ' active' : ''}`}
                onClick={() => setActiveDay(d.dayNumber)}
              >
                DAY {d.dayNumber} <span>{d.date}</span>
              </button>
            ))}
          </div>

          <div className="it-main">
            <div className="timeline active">
              {current.items.map((item, i) => (
                <div className="t-item" key={i}>
                  <div className="t-time">{item.time}</div>
                  <div className="t-body">
                    <h5>{item.title}</h5>
                    <p>{item.description}</p>
                    <div className="t-dur">{item.dur}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
