import { useRef, useState } from 'react'
import styles from './review.module.css'
import cx from '../../utils/cx.js'

// 필드명은 ItineraryEditor.jsx와 동일하게 백엔드 ItineraryDay/ItineraryItem 모델에 맞춤
export const DAYS = [
  {
    dayNumber: 1,
    date: '7/25 (목)',
    items: [
      { thumbnail: '🌋', title: '성산일출봉', description: '대표 관광지' },
      { thumbnail: '🌊', title: '섭지코지', description: '해안 산책로' },
      { thumbnail: '🍖', title: '점심 식사', description: '(현지 맛집)' },
      { thumbnail: '☕', title: '카페 다랑쉬', description: '' },
      { thumbnail: '🐷', title: '흑돼지 맛집', description: '(똔사돈 본점)' },
      { thumbnail: '🛏️', title: '숙소 체크인', description: '' },
    ],
  },
  {
    dayNumber: 2,
    date: '7/26 (금)',
    items: [
      { thumbnail: '🌲', title: '사려니숲길', description: '' },
      { thumbnail: '🏛️', title: '중문관광단지', description: '' },
      { thumbnail: '☕', title: '카페 스누피가든', description: '' },
      { thumbnail: '🍵', title: '오설록 티뮤지엄', description: '' },
      { thumbnail: '🍜', title: '저녁 식사', description: '(물회국수)' },
    ],
  },
  {
    dayNumber: 3,
    date: '7/27 (토)',
    items: [
      { thumbnail: '🏖️', title: '협재 해변', description: '' },
      { thumbnail: '🍲', title: '점심 식사', description: '(해물 뚝배기)' },
      { thumbnail: '🎨', title: '아르떼뮤지엄', description: '' },
      { thumbnail: '✈️', title: '공항 이동 및 출발', description: '' },
    ],
  },
]

export function DayNav({ activeDay, onSelect }) {
  return (
    <div className={styles.dayNav}>
      {DAYS.map((d) => (
        <button
          key={d.dayNumber}
          className={cx(styles.dayNavItem, activeDay === d.dayNumber && styles.dayNavItemActive)}
          onClick={() => onSelect(d.dayNumber)}
        >
          <div className={styles.d}>DAY {d.dayNumber}</div>
          <div className={styles.dt}>{d.date}</div>
        </button>
      ))}
    </div>
  )
}

export function DayColumns({ dayRefs }) {
  return (
    <>
      {DAYS.map((d) => (
        <div className={styles.dayCol} key={d.dayNumber} ref={(el) => (dayRefs.current[d.dayNumber] = el)}>
          <div className={styles.dayColBadge}>
            DAY {d.dayNumber} <span>{d.date}</span>
          </div>
          {d.items.map((item, i) => (
            <div className={styles.stop} key={i}>
              <div className={styles.stopThumb}>{item.thumbnail}</div>
              <div className={styles.stopBody}>
                <h5>{item.title}</h5>
                {item.description && <p>{item.description}</p>}
              </div>
            </div>
          ))}
        </div>
      ))}
    </>
  )
}

export function useDayNav() {
  const [activeDay, setActiveDay] = useState(1)
  const dayRefs = useRef({})

  const selectDay = (dayNumber) => {
    setActiveDay(dayNumber)
    dayRefs.current[dayNumber]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }

  return { activeDay, selectDay, dayRefs }
}
