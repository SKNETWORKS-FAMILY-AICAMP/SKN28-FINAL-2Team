import styles from './booking.module.css'
import cx from '../../utils/cx.js'
import { won } from '../../data/packages.js'

export default function PackageList({
  items = [],
  selected = [],
  onToggle,
  isBookmarked,
  onToggleBookmark,
}) {
  return (
    <div className={styles.card}>
      <h4>선택한 패키지</h4>

      {items.map((item) => {
        const p = item.package
        const checked = selected.includes(p.id)
        const liked = isBookmarked(p.id)

        return (
          <div
            key={item.cartId ?? p.id}
            className={cx(styles.pkgRow, checked && styles.pkgRowChecked)}
          >
            <div
              className={cx(
                styles.checkbox,
                checked && styles.checkboxChecked,
              )}
              onClick={() => onToggle?.(p.id)}
            >
              {checked ? '✓' : ''}
            </div>

            <div className={styles.pkgThumb} onClick={() => onToggle?.(p.id)}>
              {p.thumbnailUrl || p.thumbnail_url ? (
                <img
                  src={p.thumbnailUrl || p.thumbnail_url}
                  alt={p.name}
                />
              ) : (
                p.thumbnail || '🏝️'
              )}
            </div>

            <div className={styles.pkgInfo} onClick={() => onToggle?.(p.id)}>
              <h5>{p.name}</h5>
              <div className={styles.desc}>{p.description}</div>
            </div>

            <button
              className={cx(
                styles.pkgBookmark,
                liked && styles.pkgBookmarkActive,
              )}
              onClick={(e) => {
                e.stopPropagation()
                onToggleBookmark(p.id)
              }}
              aria-label="찜하기"
            >
              {liked ? '❤️' : '🤍'}
            </button>

            <div className={styles.pkgPrice} onClick={() => onToggle?.(p.id)}>
              {won(Number(p.price) * item.quantity)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
