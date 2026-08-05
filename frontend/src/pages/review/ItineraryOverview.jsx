import styles from './review.module.css'

export function DayColumns({ days }) {
  return (
    <>
      {days.map((d) => (
        <div
          className={styles.dayCol}
          key={d.dayNumber}
        >
          <div className={styles.dayColBadge}>
            DAY {d.dayNumber} <span>{d.date}</span>
          </div>

          {d.items.map((item, i) => (
            <div className={styles.stop} key={item.id ?? i}>
              <div className={styles.stopThumb}>
                {item.thumbnail ? (
                  <img
                    src={item.thumbnail}
                    alt={item.title}
                    className={styles.thumb}
                  />
                ) : (
                  '📍'
                )}
              </div>

              <div className={styles.stopBody}>
                <h5>{item.title}</h5>

                {item.description && (
                  <p>{item.description}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      ))}
    </>
  )
}