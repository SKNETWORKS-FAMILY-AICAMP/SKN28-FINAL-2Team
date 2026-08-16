import styles from './booking.module.css'
import cx from '../../utils/cx.js'

const durationLabel = (pkg) => {
  if (pkg.durationLabel || pkg.duration_label) {
    return pkg.durationLabel || pkg.duration_label
  }

  const days = Number(pkg.durationDays ?? pkg.duration_days)
  if (Number.isFinite(days) && days > 0) {
    return days === 1 ? '당일치기' : `${days - 1}박 ${days}일`
  }

  return pkg.name?.match(/\d+박\s*\d+일/)?.[0] || ''
}

export default function PackageList({
  items = [],
  selected = [],
  onToggle,
  isBookmarked,
  onToggleBookmark,
}) {
  return (
    <div className={styles.card}>
      <h4>선택한 여행 상품</h4>

      {items.map((item) => {
        const p = item.package
        const checked = selected.includes(p.id)
        const liked = isBookmarked(p.id)
        const tripDuration = durationLabel(p)
        const accommodationIncluded = Boolean(
          p.accommodationIncluded ?? p.accommodation_included ?? p.hotel,
        )
        const accommodationName =
          p.accommodationName ?? p.accommodation_name ?? p.hotel?.title ?? ''

        return (
          <div key={item.cartId ?? p.id}>
            <div
              className={cx(
                styles.pkgRow,
                checked && styles.pkgRowChecked
              )}
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

              <div
                className={styles.pkgThumb}
                onClick={() => onToggle?.(p.id)}
              >
                {p.thumbnailUrl || p.thumbnail_url ? (
                  <img
                    src={p.thumbnailUrl || p.thumbnail_url}
                    alt={p.name}
                  />
                ) : (
                  p.thumbnail || '🏝️'
                )}
              </div>

              <div
                className={styles.pkgInfo}
                onClick={() => onToggle?.(p.id)}
              >
                <h5>{p.name}</h5>
                <div className={styles.desc}>{p.description}</div>
                <div className={styles.pkgMetaList}>
                  {tripDuration && <span>{tripDuration}</span>}
                  {p.region && <span>{p.region}</span>}
                  <span>{p.isCustom ? '자유일정' : '여행사 패키지'}</span>
                  {accommodationIncluded && (
                    <span>숙소 · {accommodationName || '포함'}</span>
                  )}
                </div>
              </div>

              {!p.isCustom && (
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
              )}

              <div
                className={styles.pkgPrice}
                onClick={() => onToggle?.(p.id)}
              >
                 {(Number(p.price || 0) * item.quantity).toLocaleString('ko-KR')}원
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}