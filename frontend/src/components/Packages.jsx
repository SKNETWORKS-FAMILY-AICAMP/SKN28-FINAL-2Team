import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { won } from '../data/packages.js'
import { getPackages } from '../api/packageApi.js'
import PackageDetailModal from './PackageDetailModal.jsx'

const PACKAGE_EMOJI = {
  stay: '🏨',
  car: '🚗',
  activity: '🐴',
}

const normalizePackage = (pkg) => ({
  id: pkg.id,
  name: pkg.name,
  category: pkg.category,
  categoryLabel: pkg.category_display,
  style: pkg.style,
  styleLabel: pkg.style_display,
  description: pkg.description,
  thumbnailUrl: pkg.thumbnail_url,
  thumbnail: PACKAGE_EMOJI[pkg.category] || '🎁',
  price: Number(pkg.price),
  durationDays: pkg.duration_days,
  region: pkg.region,
  accommodationIncluded: pkg.accommodation_included,
  includedItems: Array.isArray(pkg.included_items)
    ? pkg.included_items
    : [],
  course: Array.isArray(pkg.course)
    ? pkg.course
    : [],
  isActive: pkg.is_active,
})

export default function Packages() {

  const [packages, setPackages] = useState([])
  const [selectedPackage, setSelectedPackage] = useState(null)

  useEffect(() => {
    const loadPackages = async () => {
      try {
        const data = await getPackages()

        const list = Array.isArray(data)
          ? data
          : data.results || []

        setPackages(
          list
            .slice(0, 3)
            .map(normalizePackage)
        )
      } catch (error) {
        console.error('추천 패키지 조회 실패:', error)
      }
    }

    loadPackages()
  }, [])

  return (
    <section className="packages" id="packages">
      <div className="wrap">
        <div className="reveal">
          <div className="section-tag">AI 추천 패키지</div>

          <h2 className="section-title">
            탐나플랜이 준비한
            <br />
            제주 패키지를 만나보세요.
          </h2>
        </div>

        <div className="pkg-grid">
          {packages.map((p) => (
            <div
              className="pkg"
              key={p.id}
              onClick={() => setSelectedPackage(p)}
              style={{ cursor: 'pointer' }}
            >
              <div className="pkg-img">
                {p.thumbnail}
              </div>

              <div className="pkg-body">
                <h4>{p.name}</h4>
                <div className="price">{won(p.price)}</div>
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

      <PackageDetailModal
        pkg={selectedPackage}
        onClose={() => setSelectedPackage(null)}
      />
    </section>
  )
}