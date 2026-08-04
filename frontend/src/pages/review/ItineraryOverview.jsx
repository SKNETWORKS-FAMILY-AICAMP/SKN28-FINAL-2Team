import { useRef, useState } from 'react'
import styles from './review.module.css'
import cx from '../../utils/cx.js'

export function DayNav({ days, activeDay, onSelect }) {
  return (
    <div className={styles.dayNav}>
      {days.map((d) => (
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

export function DayColumns({ days, dayRefs }) {
  return (
    <>
      {days.map((d) => (
        <div className={styles.dayCol} key={d.dayNumber} ref={(el) => (dayRefs.current[d.dayNumber] = el)}>
          <div className={styles.dayColBadge}>
            DAY {d.dayNumber} <span>{d.date}</span>
          </div>
          {d.items.map((item, i) => (
            <div className={styles.stop} key={i}>
              <div className={styles.stopThumb}>
                {item.thumbnail ? (
                  <img
                    src={item.thumbnail}
                    alt={item.title}
                    className={styles.thumb}
                  />
                ) : (
                  "📍"
                )}
              </div>
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
