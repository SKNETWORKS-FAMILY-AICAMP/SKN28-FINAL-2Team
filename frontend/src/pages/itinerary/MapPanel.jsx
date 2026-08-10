import { Link } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { getPackageRecommendations, getRoute } from '../../api/itinerary'
import styles from './itinerary.module.css'
import PackageDetailModal from '../../components/PackageDetailModal.jsx'
import { getPackageDetail, getPackages } from '../../api/packageApi.js'
const normalizePackage = (pkg) => ({
  id: pkg.id,
  packageId: pkg.package_id,
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

export default function MapPanel({ itineraryId, activeDay }) {
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const overlaysRef = useRef([])
  const infoWindowsRef = useRef([])
  const openedInfoWindowRef = useRef(null)
  const openedMarkerContentRef = useRef(null)

  const recommendationCacheKey = itineraryId ? `package-recommendations-${itineraryId}` : null
  const [routes, setRoutes] = useState([])
  const [recommendedPackages, setRecommendedPackages] = useState(() => {
    if (!itineraryId) return []

    try {
      const cached = sessionStorage.getItem(
        `package-recommendations-${itineraryId}`
      )

      return cached ? JSON.parse(cached) : []
    } catch {
      return []
    }
  })
  const [recommendationLoading, setRecommendationLoading] = useState(false)
  const [recommendationError, setRecommendationError] = useState('')
  const [packageCatalog, setPackageCatalog] = useState([])
  const [selectedPackage, setSelectedPackage] = useState(null)

  useEffect(() => {
    if (!itineraryId) return

    const loadRoute = async () => {
      try {
        const data = await getRoute(itineraryId)
        setRoutes(data)
      } catch (err) {
        console.error('경로 조회 실패:', err)
      }
    }

    loadRoute()
  }, [itineraryId])

  useEffect(() => {
  if (!itineraryId) return

  let cancelled = false

  const loadRecommendations = async () => {
    setRecommendationLoading(
      recommendedPackages.length === 0
    )
    setRecommendationError('')

    try {
      const data = await getPackageRecommendations(
        itineraryId,
        3
      )

      if (cancelled) return

      const recommendations = data.recommendations ?? []

      setRecommendedPackages(recommendations)

      if (recommendationCacheKey) {
        sessionStorage.setItem(
          recommendationCacheKey,
          JSON.stringify(recommendations)
        )
      }
    } catch (err) {
      if (cancelled) return

      console.error('추천 패키지 조회 실패:', err)

      setRecommendedPackages([])
      setRecommendationError(
        err.response?.data?.detail ??
          '추천 패키지를 불러오지 못했어요.'
      )
    } finally {
      if (!cancelled) {
        setRecommendationLoading(false)
      }
    }
  }

  loadRecommendations()

  return () => {
    cancelled = true
  }
}, [itineraryId, refreshKey])

  useEffect(() => {
    const loadPackageCatalog = async () => {
      try {
        const data = await getPackages()

        const list = Array.isArray(data)
          ? data
          : data.results ?? []

        setPackageCatalog(list.map(normalizePackage))
      } catch (err) {
        console.error('패키지 목록 조회 실패:', err)
      }
    }

    loadPackageCatalog()
  }, [])

  useEffect(() => {
    if (!window.kakao?.maps || !mapRef.current) return

    window.kakao.maps.load(() => {
      const kakao = window.kakao

      if (!mapInstanceRef.current) {
        mapInstanceRef.current = new kakao.maps.Map(mapRef.current, {
          center: new kakao.maps.LatLng(33.3617, 126.5292),
          level: 9,
        })

        kakao.maps.event.addListener(
          mapInstanceRef.current,
          'click',
          () => {
            if (openedInfoWindowRef.current) {
              openedInfoWindowRef.current.setMap(null)
              openedInfoWindowRef.current = null
              openedMarkerContentRef.current = null
            }
          }
        )
      }

      const map = mapInstanceRef.current

      overlaysRef.current.forEach((overlay) => overlay.setMap(null))
      overlaysRef.current = []

      infoWindowsRef.current.forEach((labelOverlay) => {
        labelOverlay.setMap(null)
      })

      infoWindowsRef.current = []
      openedInfoWindowRef.current = null
      openedMarkerContentRef.current = null

      const points = activeRoute?.points ?? []

      if (points.length === 0) return

      const bounds = new kakao.maps.LatLngBounds()
      const path = []

      points.forEach((point, index) => {
        const latitude = Number(point.latitude)
        const longitude = Number(point.longitude)

        if (
          !Number.isFinite(latitude) ||
          !Number.isFinite(longitude)
        ) {
          return
        }

        const position = new kakao.maps.LatLng(
          latitude,
          longitude
        )

        bounds.extend(position)
        path.push(position)

        const markerContent = document.createElement('button')

        markerContent.type = 'button'
        markerContent.textContent = String(index + 1)
        markerContent.title = point.title

        Object.assign(markerContent.style, {
          width: '30px',
          height: '30px',
          borderRadius: '50%',
          border: '2px solid #1B211D',
          background: '#2E9E62',
          color: '#FFFFFF',
          fontSize: '12px',
          fontWeight: '800',
          cursor: 'pointer',
          boxShadow: '2px 2px 0 #1B211D',
        })

        const overlay = new kakao.maps.CustomOverlay({
          position,
          content: markerContent,
          yAnchor: 1,
          zIndex: 10,
        })

        overlay.setMap(map)
        overlaysRef.current.push(overlay)

        const labelContent = document.createElement('div')

        labelContent.textContent = `${index + 1}. ${point.title}`

        Object.assign(labelContent.style, {
          minWidth: '130px',
          maxWidth: '220px',
          padding: '8px 10px',
          border: '1.5px solid #1B211D',
          background: '#FFFFFF',
          color: '#1B211D',
          fontSize: '12px',
          fontWeight: '700',
          lineHeight: '1.4',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          boxShadow: '2px 2px 0 rgba(27, 33, 29, 0.25)',
          pointerEvents: 'none',
        })

        const labelOverlay = new kakao.maps.CustomOverlay({
          position,
          content: labelContent,
          xAnchor: 0.5,
          yAnchor: 1.9,
          zIndex: 100,
        })

        infoWindowsRef.current.push(labelOverlay)

        markerContent.addEventListener('click', () => {
          const isSameMarker =
            openedMarkerContentRef.current === markerContent

          if (isSameMarker) {
            labelOverlay.setMap(null)
            openedInfoWindowRef.current = null
            openedMarkerContentRef.current = null
            return
          }

          if (openedInfoWindowRef.current) {
            openedInfoWindowRef.current.setMap(null)
          }

          labelOverlay.setMap(map)

          openedInfoWindowRef.current = labelOverlay
          openedMarkerContentRef.current = markerContent
        })
      })


      if (path.length > 0) {
        map.setBounds(bounds)
      }
    })
  }, [routes, activeDay])

  const activeRoute = routes.find(
    (route) => Number(route.day_number) === Number(activeDay)
  )
  const matchedRecommendations = recommendedPackages.map((recommendation) => ({
    recommendation,
    package: packageCatalog.find(
      (pkg) => pkg.packageId === recommendation.package_id
    ),
  }))
  const formatPrice = (price) => {
    const numericPrice = Number(price)

    if (!Number.isFinite(numericPrice)) {
      return '가격 정보 없음'
    }

    return `${numericPrice.toLocaleString('ko-KR')}원`
  }

  const handleOpenRecommendedPackage = async (matchedPackage) => {
    if (!matchedPackage?.id) return

    try {
      const data = await getPackageDetail(matchedPackage.id)
      setSelectedPackage(normalizePackage(data))
    } catch (err) {
      console.error('추천 패키지 상세 조회 실패:', err)

      alert(
        err.message ||
          '패키지 상세 정보를 불러오지 못했습니다.'
      )
    }
  }

  return (
    <>
      <div className={styles.mapCol}>
      <div className={styles.mapHead}>
        <h4>🗺️ DAY {activeDay} 동선</h4>
      </div>

      <div ref={mapRef} className={styles.mapPanel} />

      <div className={styles.pkgTitle}>
        <h4>AI 추천 패키지</h4>
        <span className={styles.badge}>일정 맞춤</span>
      </div>

      {recommendationLoading && (
        <div className={styles.pkgRecommendEmpty}>
          <strong>추천 패키지를 찾고 있어요.</strong>
          <p>
            생성된 일정과 가장 유사한 패키지를 비교하고 있어요.
          </p>
        </div>
      )}

      {!recommendationLoading && recommendationError && (
        <div className={styles.pkgRecommendEmpty}>
          <strong>추천 패키지를 불러오지 못했어요.</strong>
          <p>{recommendationError}</p>
        </div>
      )}

      {!recommendationLoading &&
        !recommendationError &&
        matchedRecommendations.length > 0 && (
          <div className={styles.pkgRecommendList}>
            {matchedRecommendations.map(({ recommendation, package: matchedPackage }) => (
              <button
                key={recommendation.package_id}
                type="button"
                className={styles.pkgRecommendCard}
                onClick={() => handleOpenRecommendedPackage(matchedPackage)}
                disabled={!matchedPackage}
              >
                {matchedPackage?.thumbnailUrl && (
                  <img
                    src={matchedPackage.thumbnailUrl}
                    alt={recommendation.title}
                    className={styles.pkgRecommendImage}
                  />
                )}

                <div className={styles.pkgRecommendBody}>
                  <strong>{recommendation.title}</strong>

                  <p>
                    {recommendation.region}
                    {' · '}
                    {recommendation.duration_days}일
                    {' · '}
                    {formatPrice(recommendation.estimated_price)}
                  </p>

                  <p>현재 여행 일정과 어울리는 추천 패키지예요.</p>
                  <span className={styles.pkgDetailLink}>
                    자세히 보기 →
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}

      {!recommendationLoading &&
        !recommendationError &&
        matchedRecommendations.length === 0 && (
          <div className={styles.pkgRecommendEmpty}>
            <strong>추천할 패키지가 아직 없어요.</strong>
            <p>
              일정에 맞는 패키지가 추가되면 이곳에 추천해드릴게요.
            </p>
          </div>
        )}
      <Link to="/packages" className={styles.pkgSeeAll}>
        전체 패키지 보러가기 →
      </Link>
    </div>

    <PackageDetailModal
      pkg={selectedPackage}
      onClose={() => setSelectedPackage(null)}
    />
  </>
  )
}