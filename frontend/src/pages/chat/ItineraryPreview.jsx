import { useState } from "react"
import styles from "../itinerary/itinerary.module.css"

export default function ItineraryPreview({ itinerary }) {
  const [activeDay, setActiveDay] = useState(
    itinerary?.days?.[0]?.dayNumber ?? 1
  )

  if (!itinerary?.days?.length) return null

  const current = itinerary.days.find(
    (day) => day.dayNumber === activeDay
  )

  if (!current) return null

  return (
    <div>
      <div className={styles.dayTabs}>
        {itinerary.days.map((day) => (
          <button
            key={day.dayNumber}
            className={`${styles.dayTab} ${
              activeDay === day.dayNumber
                ? styles.dayTabActive
                : ""
            }`}
            onClick={() => setActiveDay(day.dayNumber)}
          >
            DAY {day.dayNumber}
            <span>{day.date}</span>
          </button>
        ))}
      </div>

      <div className={styles.timeline}>
        {current.items.map((item, index) => (
          <div
            className={styles.tItem}
            key={item.id ?? index}
          >

            <div className={styles.tThumb}>
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

            <div className={styles.tBody}>
              <h5>{item.title}</h5>
              <p>{item.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}