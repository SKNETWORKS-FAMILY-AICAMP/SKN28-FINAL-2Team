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
        const color = DAY_COLORS[dayIndex % DAY_COLORS.length]
        const items = (day.items || []).filter(isPoint)
        const path = items.map((item) => {
          const position = new kakao.maps.LatLng(
            Number(item.latitude),
            Number(item.longitude),
          )
          bounds.extend(position)
          pointCount += 1
          return position
        })

        if (path.length >= 2) {
          const line = new kakao.maps.Polyline({
            path,
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
          marker.textContent = `${dayIndex + 1}-${itemIndex + 1}`
          marker.title = `${dayIndex + 1}일차 ${itemIndex + 1}. ${item.title}`

          const overlay = new kakao.maps.CustomOverlay({
            position: path[itemIndex],
            content: marker,
            yAnchor: 1,
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
