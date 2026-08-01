import { Link } from 'react-router-dom'
import { useState } from 'react'
import { PACKAGES, won, ratingLabel } from '../data/packages.js'
import { useBookmarks } from '../context/BookmarkContext.jsx'
import PackageDetailModal from './PackageDetailModal.jsx'

export default function Packages() {
  const { isBookmarked, toggle } = useBookmarks()
  const [selectedPackage, setSelectedPackage] = useState(null)

  return (
    <section className="packages" id="packages">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">AI 추천 패키지</div>
          <h2 className="section-title">
            내 일정과 가장 잘 맞는
            <br />
            추천 패키지를 만나보세요.
          </h2>
        </div>
        <div className="pkg-grid">
          {PACKAGES.map((p) => (
            <div className="pkg reveal" key={p.id} onClick={() => setSelectedPackage(p)} style={{ cursor: 'pointer' }}>
              <div className="pkg-img">
                {p.thumbnail}
                <button
                  className={`pkg-bookmark${isBookmarked(p.id) ? ' active' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    toggle(p.id)
                  }}
                  aria-label="찜하기"
                >
                  {isBookmarked(p.id) ? '❤️' : '🤍'}
                </button>
              </div>
              <div className="pkg-body">
                <div className="rating">{ratingLabel(p)}</div>
                <h4>{p.name}</h4>
                <div className="price">{won(p.price)} ~</div>
              </div>
            </div>
          ))}
        </div>
        <div className="pkg-see-all-wrap">
          <Link to="/packages" className="btn ghost">
            전체 패키지 보러가기 →
          </Link>
        </div>
      </div>
      <PackageDetailModal pkg={selectedPackage} onClose={() => setSelectedPackage(null)} />
    </section>
  )
}