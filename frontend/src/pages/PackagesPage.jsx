import { useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './packages/packages.module.css'
import cx from '../utils/cx.js'
import AccountMenu from '../components/AccountMenu.jsx'
import PackageDetailModal from '../components/PackageDetailModal.jsx'
import { PACKAGES, won, ratingLabel } from '../data/packages.js'
import { useBookmarks } from '../context/BookmarkContext.jsx'

const FILTERS = [
  { value: 'all', label: '전체' },
  { value: 'stay', label: '숙소' },
  { value: 'car', label: '렌터카' },
  { value: 'activity', label: '액티비티' },
]

export default function PackagesPage() {
  const [filter, setFilter] = useState('all')
  const [selectedPackage, setSelectedPackage] = useState(null)
  const { isBookmarked, toggle } = useBookmarks()

  const visible = filter === 'all' ? PACKAGES : PACKAGES.filter((p) => p.category === filter)

  return (
    <div className={styles.page}>
      <header className={styles.appnav}>
        <Link to="/" className={styles.logo}>
          <span className={styles.logoMark}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
              <path d="M12 2c4 3 6 7 6 11a6 6 0 0 1-12 0c0-4 2-8 6-11z" fill="#fff" />
            </svg>
          </span>
          탐나플랜
        </Link>
        <AccountMenu />
      </header>

      <div className={styles.wrap}>
        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 추천 패키지</div>
          <h1>탐나플랜이 준비한 패키지 전체보기</h1>
          <p>숙소·렌터카·액티비티를 한눈에 비교하고, 마음에 드는 패키지는 하트로 찜해보세요.</p>
        </div>

        <div className={styles.filters}>
          {FILTERS.map((f) => (
            <button
              key={f.value}
              className={cx(styles.filterBtn, filter === f.value && styles.filterBtnActive)}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {visible.length === 0 ? (
          <div className={styles.empty}>해당 카테고리의 패키지가 아직 없어요.</div>
        ) : (
          <div className={styles.grid}>
            {visible.map((p) => (
              <div className={styles.card} key={p.id} onClick={() => setSelectedPackage(p)}>
                <div className={styles.cardImg}>
                  {p.thumbnail}
                  <span className={styles.cardBadge}>{p.categoryLabel}</span>
                  <button
                    className={cx(styles.bookmarkBtn, isBookmarked(p.id) && styles.bookmarkBtnActive)}
                    onClick={(e) => {
                      e.stopPropagation()
                      toggle(p.id)
                    }}
                    aria-label="찜하기"
                  >
                    {isBookmarked(p.id) ? '❤️' : '🤍'}
                  </button>
                </div>
                <div className={styles.cardBody}>
                  <div className={styles.rating}>{ratingLabel(p)}</div>
                  <h4>{p.name}</h4>
                  <p className={styles.desc}>{p.description}</p>
                  <div className={styles.tags}>
                    {p.includedItems.map((item) => (
                      <span className={styles.tag} key={item}>
                        #{item}
                      </span>
                    ))}
                  </div>
                  <div className={styles.cardFoot}>
                    <div className={styles.price}>{won(p.price)}</div>
                    <Link to="/booking" className={styles.btn} onClick={(e) => e.stopPropagation()}>
                      예약하기 →
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <PackageDetailModal pkg={selectedPackage} onClose={() => setSelectedPackage(null)} />
    </div>
  )
}
