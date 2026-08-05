import { useEffect, useRef } from "react";
import { getRoute } from "../../api/itinerary";
import styles from "./review.module.css";

export default function TripSummary({ itinerary }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const polylinesRef = useRef([]);

  useEffect(() => {
    const loadRoute = async () => {
      if (!itinerary?.id) return;

      try {
        const route = await getRoute(itinerary.id);

        if (!window.kakao?.maps || !mapRef.current) return;

        window.kakao.maps.load(() => {
          const kakao = window.kakao;

          // 지도는 한 번만 생성
          if (!mapInstanceRef.current) {
            mapInstanceRef.current = new kakao.maps.Map(
              mapRef.current,
              {
                center: new kakao.maps.LatLng(
                  33.3617,
                  126.5292
                ),
                level: 10,
              }
            );
          }

          const map = mapInstanceRef.current;

          // 기존 마커 제거
          markersRef.current.forEach((marker) => {
            marker.setMap(null);
          });
          markersRef.current = [];

          // 기존 경로선 제거
          polylinesRef.current.forEach((polyline) => {
            polyline.setMap(null);
          });
          polylinesRef.current = [];

          const bounds = new kakao.maps.LatLngBounds();
          const dayColors = [
            "#E53935",
            "#2563EB",
            "#F59E0B",
          ];

          let hasPoint = false;

          route.forEach((day, dayIndex) => {
            const sortedPoints = [...(day.points ?? [])].sort(
              (a, b) => Number(a.order) - Number(b.order)
            );

            const path = [];

            sortedPoints.forEach((point) => {
              const latitude = Number(point.latitude);
              const longitude = Number(point.longitude);

              if (
                !Number.isFinite(latitude) ||
                !Number.isFinite(longitude)
              ) {
                return;
              }

              const position = new kakao.maps.LatLng(
                latitude,
                longitude
              );

              path.push(position);
              bounds.extend(position);
              hasPoint = true;
            });

            // 날짜별 경로선
            if (path.length >= 2) {
              const polyline = new kakao.maps.Polyline({
                path,
                strokeWeight: 8,
                strokeColor:
                  dayColors[dayIndex % dayColors.length],
                strokeOpacity: 1,
                strokeStyle: "solid",
              });

              polyline.setMap(map);
              polylinesRef.current.push(polyline);
            }

            // 경로선 생성 후 마커 표시
            sortedPoints.forEach((point) => {
              const latitude = Number(point.latitude);
              const longitude = Number(point.longitude);

              if (
                !Number.isFinite(latitude) ||
                !Number.isFinite(longitude)
              ) {
                return;
              }

              const position = new kakao.maps.LatLng(
                latitude,
                longitude
              );

              const marker = new kakao.maps.Marker({
                map,
                position,
                title: `DAY ${day.day_number} - ${point.title}`,
              });

              markersRef.current.push(marker);
            });
          });

          if (hasPoint) {
            map.setBounds(bounds);

            // 카드 레이아웃 반영 후 지도 다시 계산
            requestAnimationFrame(() => {
              kakao.maps.event.trigger(map, "resize");
              map.setBounds(bounds);
            });
          }
        });
      } catch (error) {
        console.error("여행 경로 조회 실패:", error);
      }
    };

    loadRoute();

    return () => {
      markersRef.current.forEach((marker) => {
        marker.setMap(null);
      });

      polylinesRef.current.forEach((polyline) => {
        polyline.setMap(null);
      });

      markersRef.current = [];
      polylinesRef.current = [];
    };
  }, [itinerary?.id]);

  return (
    <div className={styles.summary}>
      <h4>여행 요약</h4>

      <div
        ref={mapRef}
        className={styles.mapPanel}
      />

      <div className={styles.summaryLabel}>
        여행 기간
      </div>

      <div className={styles.summaryRow}>
        <span className={styles.v}>
          {itinerary.startDate} ~ {itinerary.endDate} ·{" "}
          {itinerary.durationLabel}
        </span>
      </div>
    </div>
  );
}