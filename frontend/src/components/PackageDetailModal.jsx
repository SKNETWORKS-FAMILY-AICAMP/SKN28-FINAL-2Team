import { useNavigate } from 'react-router-dom'
import styles from './PackageDetailModal.module.css'
import cx from '../utils/cx.js'
import { won, ratingLabel } from '../data/packages.js'
import { useBookmarks } from '../context/BookmarkContext.jsx'
import { useCart } from '../context/CartContext.jsx'

const STYLE_LABEL = {
  healing: '힐링',
  family: '가족여행',
  activity: '액티비티',
}

export default function PackageDetailModal({ pkg, onClose }) {
  const { isBookmarked, toggle } = useBookmarks()
  const { addToCart, openCart } = useCart()
  const navigate = useNavigate()

  if (!pkg) return null

  const handleAddToCart = () => {
    addToCart(pkg.id)
    onClose()
    openCart()
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <button className={styles.closeBtn} onClick={onClose} aria-label="닫기">
          ✕
        </button>

        <div className={styles.hero}>
          <span className={styles.heroEmoji}>{pkg.thumbnail}</span>
          <span className={styles.heroBadge}>{pkg.categoryLabel}</span>
          <button
            className={cx(styles.bookmarkBtn, isBookmarked(pkg.id) && styles.bookmarkBtnActive)}
            onClick={() => toggle(pkg.id)}
            aria-label="찜하기"
          >
            {isBookmarked(pkg.id) ? '❤️' : '🤍'}
          </button>
        </div>

        <div className={styles.body}>
          <div className={styles.rating}>{ratingLabel(pkg)}</div>
          <h2>{pkg.name}</h2>
          <p className={styles.desc}>{pkg.description}</p>

          <div className={styles.infoGrid}>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>📅 기간</span>
              <span className={styles.infoValue}>{pkg.durationDays}일</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>🏨 숙박 포함</span>
              <span className={styles.infoValue}>{pkg.accommodationIncluded ? '포함' : '미포함'}</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>✨ 여행 스타일</span>
              <span className={styles.infoValue}>{STYLE_LABEL[pkg.style] || pkg.style}</span>
            </div>
          </div>

          <div className={styles.section}>
            <h4>포함 사항</h4>
            <ul className={styles.includeList}>
              {pkg.includedItems.map((item) => (
                <li key={item}>
                  <span className={styles.check}>✓</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className={styles.footer}>
          <div className={styles.priceBlock}>
            <span className={styles.priceLabel}>1인 기준</span>
            <span className={styles.price}>{won(pkg.price)}</span>
          </div>
          <div className={styles.footActions}>
            <button className={cx(styles.btn, styles.ghost)} onClick={handleAddToCart}>
              🛒 담기
            </button>
            <button
              className={cx(styles.btn, styles.primary)}
              onClick={() => {
                onClose()
                navigate('/booking')
              }}
            >
              예약하기 →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
