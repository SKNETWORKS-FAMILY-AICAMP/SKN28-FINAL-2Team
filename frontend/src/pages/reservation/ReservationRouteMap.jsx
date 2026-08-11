import { useEffect, useRef } from 'react'

import styles from './reservationDetail.module.css'

const DAY_COLORS = ['#4E9F79', '#F08A72', '#5B8FD1', '#9B7BC4', '#D9A441']

const isPoint = (item) =>
  Number.isFinite(Number(item?.latitude)) &&
  Number.isFinite(Number(item?.longitude))

export default function ReservationRouteMap({ days = [] }) {
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const overlaysRef = useRef([])
  const polylinesRef = useRef([])

  useEffect(() => {
    if (!window.kakao?.maps || !mapRef.current) return undefined

    window.kakao.maps.load(() => {
      const kakao = window.kakao

      if (!mapInstanceRef.current) {
        mapInstanceRef.current = new kakao.maps.Map(mapRef.current, {
          center: new kakao.maps.LatLng(33.3617, 126.5292),
          level: 10,
        })
      }

      const map = mapInstanceRef.current
      overlaysRef.current.forEach((overlay) => overlay.setMap(null))
      polylinesRef.current.forEach((line) => line.setMap(null))
      overlaysRef.current = []
      polylinesRef.current = []

      const bounds = new kakao.maps.LatLngBounds()
      let pointCount = 0

      days.forEach((day, dayIndex) => {
        const dayNumber = Number(
          day.day ?? day.day_number ?? dayIndex + 1
        )

        const color =
          DAY_COLORS[(dayNumber - 1) % DAY_COLORS.length]

        const items = (day.items || [])
          .filter(isPoint)
          .sort(
            (a, b) =>
              Number(a.sequence ?? a.order ?? 0) -
              Number(b.sequence ?? b.order ?? 0)
          )

        const itemPositions = items.map((item) => {
          const position = new kakao.maps.LatLng(
            Number(item.latitude),
            Number(item.longitude),
          )

          bounds.extend(position)
          pointCount += 1

          return position
        })

        const roadPoints = (day.path || []).filter(isPoint)

        const routePath =
          roadPoints.length >= 2
            ? roadPoints.map((point) => {
                const position = new kakao.maps.LatLng(
                  Number(point.latitude),
                  Number(point.longitude),
                )

                bounds.extend(position)

                return position
              })
            : itemPositions

        if (routePath.length >= 2) {
          const line = new kakao.maps.Polyline({
            path: routePath,
            strokeWeight: 6,
            strokeColor: color,
            strokeOpacity: 0.88,
            strokeStyle: 'solid',
          })

          line.setMap(map)
          polylinesRef.current.push(line)
        }

        items.forEach((item, itemIndex) => {
          const marker = document.createElement('div')

          marker.className = styles.mapMarker
          marker.style.backgroundColor = color
          marker.textContent =
            `${dayNumber}-${itemIndex + 1}`

          marker.title =
            `${dayNumber}일차 ${itemIndex + 1}. ${item.title}`

          const overlay = new kakao.maps.CustomOverlay({
            position: itemPositions[itemIndex],
            content: marker,
            yAnchor: 1,
            zIndex: 10 + itemIndex,
          })

          overlay.setMap(map)
          overlaysRef.current.push(overlay)
        })
      })

      if (pointCount > 0) {
        map.setBounds(bounds)
        requestAnimationFrame(() => {
          kakao.maps.event.trigger(map, 'resize')
          map.setBounds(bounds)
        })
      }
    })

    return () => {
      overlaysRef.current.forEach((overlay) => overlay.setMap(null))
      polylinesRef.current.forEach((line) => line.setMap(null))
      overlaysRef.current = []
      polylinesRef.current = []
    }
  }, [days])

  const hasCoordinates = days.some((day) => (day.items || []).some(isPoint))

  if (!hasCoordinates) {
    return (
      <div className={styles.mapEmpty}>
        <span>🗺️</span>
        <p>표시할 위치 정보가 없습니다.</p>
      </div>
    )
  }

  return <div ref={mapRef} className={styles.mapCanvas} />
}
