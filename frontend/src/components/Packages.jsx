import { PACKAGES, won, ratingLabel } from '../data/packages.js'
import { useBookmarks } from '../context/BookmarkContext.jsx'

export default function Packages() {
  const { isBookmarked, toggle } = useBookmarks()

  return (
    <section className="packages" id="packages">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">AI 추천 패키지</div>
          <h2 className="section-title">
            일정에 딱 맞는
            <br />
            숙소·렌터카를 골라드려요
          </h2>
        </div>
        <div className="pkg-grid">
          {PACKAGES.map((p) => (
            <div className="pkg reveal" key={p.id}>
              <div className="pkg-img">
                {p.thumbnail}
                <button
                  className={`pkg-bookmark${isBookmarked(p.id) ? ' active' : ''}`}
                  onClick={() => toggle(p.id)}
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
      </div>
    </section>
  )
}
