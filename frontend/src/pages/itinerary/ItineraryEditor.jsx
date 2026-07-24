import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import styles from './itinerary.module.css'
import cx from '../../utils/cx.js'

const DAYS = [
  {
    day: 1,
    date: '7/25 (목)',
    total: '129,000원',
    items: [
      { time: '09:30', thumb: '🌋', title: '성산일출봉', desc: '일출 명소로 유명한 대표 관광지' },
      { time: '12:00', thumb: '🏖️', title: '협재해변', desc: '에메랄드빛 바다 · 산책하기 좋은 해변' },
      { time: '13:30', thumb: '🍖', title: '점심 식사 — 흑돼지 맛집', desc: '현지 맛집 추천 · 흑돼지 정식' },
      { time: '15:30', thumb: '🍵', title: '오설록 티뮤지엄', desc: '녹차밭 산책과 티하우스 체험' },
      { time: '17:30', thumb: '🛏️', title: '숙소 체크인', desc: '제주 오션뷰 호텔' },
    ],
  },
  {
    day: 2,
    date: '7/26 (금)',
    total: '168,000원',
    items: [
      { time: '09:00', thumb: '🌲', title: '사려니숲길', desc: '편백나무 향 가득한 여유로운 산책로' },
      { time: '11:00', thumb: '🏮', title: '동문관덕정', desc: '제주 전통 시장 골목 구경' },
      { time: '12:30', thumb: '🍖', title: '흑돼지 맛집', desc: '현지인 추천 흑돼지 맛집' },
      { time: '14:30', thumb: '☕', title: '카페 스누피가든', desc: '사진 찍기 좋은 테마 카페 겸 정원' },
      { time: '19:00', thumb: '🍜', title: '저녁 식사 — 물회국수', desc: '제주식 시원한 물회 한 그릇' },
    ],
  },
  {
    day: 3,
    date: '7/27 (토)',
    total: '141,700원',
    items: [
      { time: '09:00', thumb: '🏖️', title: '협재 해변 산책', desc: '마지막 날 아침 여유로운 바다 산책' },
      { time: '11:00', thumb: '🍲', title: '점심 식사 — 해물뚝배기', desc: '떠나기 전 든든한 한 끼' },
      { time: '13:00', thumb: '🎨', title: '아르떼뮤지엄', desc: '몰입형 미디어아트 전시로 마무리' },
      { time: '16:00', thumb: '✈️', title: '공항 이동 및 출국', desc: '렌터카 반납 후 공항으로 이동' },
    ],
  },
]

export default function ItineraryEditor() {
  const [activeDay, setActiveDay] = useState(1)
  const navigate = useNavigate()
  const current = DAYS.find((d) => d.day === activeDay)

  return (
    <div className={styles.itCol}>
      <div className={styles.itTop}>
        <div>
          <div className={styles.sectionTag}>✓ 일정 확인 및 수정</div>
          <h1>제주 2박 3일 힐링 여행</h1>
          <p>부모님과 함께 · 2024.07.25(목) – 07.27(토) · 2인 · 1인당 약 50만원</p>
        </div>
        <button className={cx(styles.btn, styles.ghost, styles.sm)}>🔄 일정 다시 생성</button>
      </div>

      <div className={styles.dayTabs}>
        {DAYS.map((d) => (
          <button
            key={d.day}
            className={cx(styles.dayTab, activeDay === d.day && styles.dayTabActive)}
            onClick={() => setActiveDay(d.day)}
          >
            DAY {d.day} <span>{d.date}</span>
          </button>
        ))}
      </div>

      <div className={styles.timeline}>
        {current.items.map((item, i) => (
          <div className={styles.tItem} key={i}>
            <div className={styles.tTime}>{item.time}</div>
            <div className={styles.tThumb}>{item.thumb}</div>
            <div className={styles.tBody}>
              <h5>{item.title}</h5>
              <p>{item.desc}</p>
            </div>
            <button className={styles.tMenu}>⋮</button>
          </div>
        ))}
        <button className={styles.addSpot}>+ 장소 추가</button>
        <div className={styles.itTotal}>
          <div className={styles.lbl}>Day {current.day} 예상 비용</div>
          <div className={styles.val}>{current.total}</div>
        </div>
      </div>

      <div className={styles.itActions}>
        <Link to="/chat" className={cx(styles.btn, styles.ghost)}>
          이전 단계로
        </Link>
        <button className={cx(styles.btn, styles.primary)} onClick={() => navigate('/review')}>
          이 일정으로 확정하기 →
        </button>
      </div>
    </div>
  )
}
