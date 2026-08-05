import { Link } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { getRoute } from '../../api/itinerary'
import styles from './itinerary.module.css'

export default function MapPanel({ itineraryId, activeDay, refreshKey }) {
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const overlaysRef = useRef([])
  const infoWindowsRef = useRef([])
  const openedInfoWindowRef = useRef(null)
  const openedMarkerContentRef = useRef(null)

  const [routes, setRoutes] = useState([])

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
  }, [itineraryId, refreshKey])

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

  return (
    <div className={styles.mapCol}>
      <div className={styles.mapHead}>
        <h4>🗺️ DAY {activeDay} 동선</h4>
      </div>

      <div ref={mapRef} className={styles.mapPanel} />

      <div className={styles.pkgTitle}>
        <h4>AI 추천 패키지</h4>
        <span className={styles.badge}>일정 맞춤</span>
      </div>

      <div className={styles.pkgRecommendEmpty}>
        <strong>추천 패키지를 준비 중이에요.</strong>
        <p>
          일정 생성이 완료되면 패키지 중 가장 유사한 패키지를
          추천해드릴게요.
        </p>
      </div>

      <Link to="/packages" className={styles.pkgSeeAll}>
        전체 패키지 보러가기 →
      </Link>
    </div>
  )
}