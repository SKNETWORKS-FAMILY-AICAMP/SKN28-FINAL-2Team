import { useNavigate } from 'react-router-dom'
import styles from './PackageDetailModal.module.css'
import cx from '../utils/cx.js'
import { won } from '../data/packages.js'
import { useBookmarks } from '../context/BookmarkContext.jsx'
import { useCart } from '../context/CartContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const STYLE_LABEL = {
  healing: '힐링',
  family: '가족여행',
  activity: '액티비티',
}

export default function PackageDetailModal({ pkg, onClose }) {
  const { isBookmarked, toggle } = useBookmarks()
  const { addToCart, openCart } = useCart()
  const navigate = useNavigate()
  const { isLoggedIn } = useAuth()

  if (!pkg) return null

  const handleAddToCart = () => {
    if (!isLoggedIn) {
      alert('로그인 후 이용할 수 있습니다.')
      return
    }

    addToCart(pkg.id)
    onClose()
    openCart()
  }

  const handleBooking = () => {
    if (!isLoggedIn) {
      alert('로그인 후 이용할 수 있습니다.')
      return
    }

    onClose()

    navigate('/booking', {
      state: {
        bookingSource: 'package',
        packageIds: [pkg.id],
        packages: [pkg],
      },
    })
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <button className={styles.closeBtn} onClick={onClose} aria-label="닫기">
          ✕
        </button>

        <div className={styles.hero}>
          {pkg.thumbnailUrl ? (
            <img
              src={pkg.thumbnailUrl}
              alt={pkg.name}
              className={styles.heroImage}
            />
          ) : (
            <span className={styles.heroEmoji}>{pkg.thumbnail}</span>
          )}
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
          <h2>{pkg.name}</h2>
          <p className={styles.desc}>{pkg.description}</p>

          <div className={styles.infoGrid}>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>📅 기간</span>
              <span className={styles.infoValue}>{pkg.durationDays}일</span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>🏨 숙박 포함</span>
              <span className={styles.infoValue}>
                {pkg.accommodationIncluded
                  ? (pkg.accommodationName || '포함')
                  : '미포함'}
              </span>
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
          {pkg.course.length > 0 && (
            <div className={styles.section}>
              <h4>일정별 코스</h4>

              <div className={styles.courseList}>
                {pkg.course.map((dayCourse) => (
                  <div className={styles.courseDay} key={dayCourse.day}>
                    <div className={styles.dayTitle}>
                      Day {dayCourse.day}
                    </div>

                    <div className={styles.courseItems}>
                      {dayCourse.items.map((item) => (
                        <div
                          className={styles.courseItem}
                          key={`${dayCourse.day}-${item.sequence}-${item.content_id}`}
                        >
                          <div className={styles.courseSequence}>
                            {item.sequence}
                          </div>

                          <div className={styles.courseInfo}>
                            <strong>{item.title}</strong>

                            {item.address && (
                              <span>{item.address}</span>
                            )}

                            <small>
                              {item.item_type === 'restaurant'
                                ? '🍽️ 음식점'
                                : item.item_type === 'hotel'
                                  ? '🏨 숙소'
                                  : '📍 관광지'}
                            </small>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
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
              onClick={handleBooking}
            >
              예약하기 →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
