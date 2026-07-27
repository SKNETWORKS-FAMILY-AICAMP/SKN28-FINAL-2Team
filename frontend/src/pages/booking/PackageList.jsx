import styles from './booking.module.css'
import cx from '../../utils/cx.js'
import { PACKAGES, won, ratingLabel } from '../../data/packages.js'

export default function PackageList({ selected, onToggle, isBookmarked, onToggleBookmark }) {
  return (
    <div className={styles.card}>
      <h4>선택한 패키지</h4>
      {PACKAGES.map((p) => {
        const checked = selected.includes(p.id)
        const liked = isBookmarked(p.id)
        return (
          <div key={p.id} className={cx(styles.pkgRow, checked && styles.pkgRowChecked)}>
            <div className={cx(styles.checkbox, checked && styles.checkboxChecked)} onClick={() => onToggle(p.id)}>
              {checked ? '✓' : ''}
            </div>
            <div className={styles.pkgThumb} onClick={() => onToggle(p.id)}>
              {p.thumbnail}
            </div>
            <div className={styles.pkgInfo} onClick={() => onToggle(p.id)}>
              <h5>{p.name}</h5>
              <div className={styles.desc}>{p.description}</div>
              <div className={styles.rating}>{ratingLabel(p)}</div>
            </div>
            <button
              className={cx(styles.pkgBookmark, liked && styles.pkgBookmarkActive)}
              onClick={(e) => {
                e.stopPropagation()
                onToggleBookmark(p.id)
              }}
              aria-label="찜하기"
            >
              {liked ? '❤️' : '🤍'}
            </button>
            <div className={styles.pkgPrice} onClick={() => onToggle(p.id)}>
              {won(p.price)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
