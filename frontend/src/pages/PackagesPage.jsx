import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import styles from './packages/packages.module.css'
import cx from '../utils/cx.js'
import AccountMenu from '../components/AccountMenu.jsx'
import PackageDetailModal from '../components/PackageDetailModal.jsx'
import { won } from '../data/packages.js'
import { getPackages, getPackageDetail, } from '../api/packageApi.js'
import { useBookmarks } from '../context/BookmarkContext.jsx'

const FILTERS = [
  { value: 'all', label: '전체' },
  { value: 1, label: '당일' },
  { value: 2, label: '1박 2일' },
  { value: 3, label: '2박 3일' },
  { value: 4, label: '3박 4일' },
  { value: 5, label: '4박 5일' },
]

const normalizePackage = (pkg) => ({
  id: pkg.id,
  name: pkg.name,
  category: pkg.category,
  categoryLabel: pkg.category_display,
  style: pkg.style,
  styleLabel: pkg.style_display,
  description: pkg.description,
  thumbnailUrl: pkg.thumbnail_url,
  price: Number(pkg.price),
  durationDays: pkg.duration_days,
  region: pkg.region,
  accommodationIncluded: pkg.accommodation_included,
  accommodationName: pkg.accommodation_name || '',
  includedItems: Array.isArray(pkg.included_items)
    ? pkg.included_items
    : [],
  course: Array.isArray(pkg.course)
    ? pkg.course
    : [],
  rating: Number(pkg.rating),
  reviewCount: pkg.review_count,
  isActive: pkg.is_active,
})

export default function PackagesPage() {
  const navigate = useNavigate()
  const { isLoggedIn } = useAuth()
  const [filter, setFilter] = useState('all')
  const [selectedPackage, setSelectedPackage] = useState(null)
  const [packages, setPackages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const itemsPerPage = 9
  const { isBookmarked, toggle } = useBookmarks()
  useEffect(() => {
  const loadPackages = async () => {
    try {
      setLoading(true)
      setError('')

      const data = await getPackages()
      const list = Array.isArray(data)
        ? data
        : data.results || []

      setPackages(list.map(normalizePackage))
    } catch (err) {
      console.error('패키지 목록 조회 실패:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  loadPackages()
}, [])

  const handleOpenDetail = async (id) => {
    try {
      const data = await getPackageDetail(id)
      setSelectedPackage(normalizePackage(data))
    } catch (err) {
      console.error('패키지 상세 조회 실패:', err)
      alert(err.message || '패키지 상세 정보를 불러오지 못했습니다.')
    }
  }
  const handleDirectBooking = (e, pkg) => {
    e.stopPropagation()

    if (!isLoggedIn) {
      alert('로그인 후 이용할 수 있습니다.')
      return
    }

    navigate('/booking', {
      state: {
        bookingSource: 'package',
        packageIds: [pkg.id],
        packages: [pkg],
      },
    })
  }

  const filtered =
    filter === 'all'
      ? packages
      : packages.filter((p) => Number(p.durationDays) === Number(filter))

  const totalPages = Math.ceil(filtered.length / itemsPerPage)

  const visible =
    filter === 'all'
      ? packages.slice((page - 1) * itemsPerPage, page * itemsPerPage)
      : filtered

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
        <p>여행 기간에 맞는 패키지를 한눈에 비교하고, 마음에 드는 패키지는 하트로 찜해보세요.</p>
      </div>

      <div className={styles.filters}>
        {FILTERS.map((f) => (
          <button
            key={f.value}
            className={cx(styles.filterBtn, filter === f.value && styles.filterBtnActive)}
            onClick={() => {setFilter(f.value), setPage(1)}}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className={styles.empty}>패키지를 불러오는 중...</div>
      ) : error ? (
        <div className={styles.empty}>{error}</div>
      ) : visible.length === 0 ? (
        <div className={styles.empty}>해당 기간의 패키지가 아직 없어요.</div>
      ) : (
        <>
          <div className={styles.grid}>
            {visible.map((p) => (
              <div
                className={styles.card}
                key={p.id}
                onClick={() => handleOpenDetail(p.id)}
              >
                <div className={styles.cardImg}>
                  <img
                    src={p.thumbnailUrl}
                    alt={p.name}
                    className={styles.cardImage}
                  />

                  <span className={styles.cardBadge}> {p.styleLabel} </span>

                  <button
                    className={cx(
                      styles.bookmarkBtn,
                      isBookmarked(p.id) && styles.bookmarkBtnActive
                    )}
                    onClick={(e) => {
                      e.stopPropagation()
                      toggle(p.id)
                    }}
                    aria-label="찜하기"
                  >
                    {isBookmarked(p.id) ? "❤️" : "🤍"}
                  </button>
                </div>

                <div className={styles.cardBody}>
                  <h4>{p.name}</h4>

                  <p className={styles.desc}>{p.description}</p>

                  <div className={styles.tags}>
                    {p.accommodationName && (
                      <span className={styles.tag}>🏨 {p.accommodationName}</span>
                    )}
                    {p.includedItems.map((item) => (
                      <span className={styles.tag} key={item}>
                        #{item}
                      </span>
                    ))}
                  </div>

                  <div className={styles.cardFoot}>
                    <div className={styles.price}>{won(p.price)}</div>

                    <button
                      type="button"
                      className={styles.btn}
                      onClick={(e) => handleDirectBooking(e, p)}
                    >
                      예약하기 →
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filter === 'all' && (       
            <div className={styles.pagination}>
              <button
                disabled={page === 1}
                onClick={() => setPage(1)}
              >
                {"<<"}
              </button>

              <button
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                {"<"}
              </button>

              {Array.from({ length: totalPages }, (_, i) => (
                <button
                  key={i + 1}
                  className={page === i + 1 ? styles.pageActive : ""}
                  onClick={() => setPage(i + 1)}
                >
                  {i + 1}
                </button>
              ))}

              <button
                disabled={page === totalPages}
                onClick={() => setPage(page + 1)}
              >
                {">"}
              </button>

              <button
                disabled={page === totalPages}
                onClick={() => setPage(totalPages)}
              >
                {">>"}
              </button>
            </div>
          )}
        </>
      )}
    </div>

    <PackageDetailModal
      pkg={selectedPackage}
      onClose={() => setSelectedPackage(null)}
    />
  </div>
)
}
