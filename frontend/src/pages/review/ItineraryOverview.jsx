import { useRef, useState } from 'react'
import styles from './review.module.css'
import cx from '../../utils/cx.js'

export const DAYS = [
  {
    day: 1,
    date: '7/25 (목)',
    stops: [
      { thumb: '🌋', title: '성산일출봉', note: '대표 관광지' },
      { thumb: '🌊', title: '섭지코지', note: '해안 산책로' },
      { thumb: '🍖', title: '점심 식사', note: '(현지 맛집)' },
      { thumb: '☕', title: '카페 다랑쉬', note: '' },
      { thumb: '🐷', title: '흑돼지 맛집', note: '(똔사돈 본점)' },
      { thumb: '🛏️', title: '숙소 체크인', note: '' },
    ],
  },
  {
    day: 2,
    date: '7/26 (금)',
    stops: [
      { thumb: '🌲', title: '사려니숲길', note: '' },
      { thumb: '🏛️', title: '중문관광단지', note: '' },
      { thumb: '☕', title: '카페 스누피가든', note: '' },
      { thumb: '🍵', title: '오설록 티뮤지엄', note: '' },
      { thumb: '🍜', title: '저녁 식사', note: '(물회국수)' },
    ],
  },
  {
    day: 3,
    date: '7/27 (토)',
    stops: [
      { thumb: '🏖️', title: '협재 해변', note: '' },
      { thumb: '🍲', title: '점심 식사', note: '(해물 뚝배기)' },
      { thumb: '🎨', title: '아르떼뮤지엄', note: '' },
      { thumb: '✈️', title: '공항 이동 및 출발', note: '' },
    ],
  },
]

export function DayNav({ activeDay, onSelect }) {
  return (
    <div className={styles.dayNav}>
      {DAYS.map((d) => (
        <button
          key={d.day}
          className={cx(styles.dayNavItem, activeDay === d.day && styles.dayNavItemActive)}
          onClick={() => onSelect(d.day)}
        >
          <div className={styles.d}>DAY {d.day}</div>
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
        <div className={styles.dayCol} key={d.day} ref={(el) => (dayRefs.current[d.day] = el)}>
          <div className={styles.dayColBadge}>
            DAY {d.day} <span>{d.date}</span>
          </div>
          {d.stops.map((s, i) => (
            <div className={styles.stop} key={i}>
              <div className={styles.stopThumb}>{s.thumb}</div>
              <div className={styles.stopBody}>
                <h5>{s.title}</h5>
                {s.note && <p>{s.note}</p>}
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

  const selectDay = (day) => {
    setActiveDay(day)
    dayRefs.current[day]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }

  return { activeDay, selectDay, dayRefs }
}
