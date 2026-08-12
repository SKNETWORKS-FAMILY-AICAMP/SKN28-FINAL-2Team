import { useEffect, useRef, useState } from 'react';

import { getRoute } from '../../api/itinerary';
import styles from './review.module.css';

const validPoint = (point) =>
  Number.isFinite(Number(point?.latitude)) &&
  Number.isFinite(Number(point?.longitude));

const DAY_COLORS = [
  '#4E9F79',
  '#F08A72',
  '#5B8FD1',
  '#9B7BC4',
  '#D9A441',
];

const dayColor = (dayNumber) =>
  DAY_COLORS[(Number(dayNumber) - 1) % DAY_COLORS.length];

export default function ComparisonRouteMap({
  itineraryId,
  storedDays = [],
  mode = 'compare',
}) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const overlaysRef = useRef([]);
  const polylinesRef = useRef([]);

  const [customRoutes, setCustomRoutes] = useState([]);

  const [activeProduct, setActiveProduct] = useState(
    mode === 'custom' ? 'custom' : 'stored'
  );

  const currentProduct =
    mode === 'stored'
      ? 'stored'
      : mode === 'custom'
        ? 'custom'
        : activeProduct;

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const routes = await getRoute(itineraryId);

        if (cancelled) return;

        setCustomRoutes(routes);
      } catch (error) {
        console.error(
          '비교 지도 경로 조회 실패:',
          error
        );
      }
    };

    if (itineraryId) {
      load();
    }

    return () => {
      cancelled = true;
    };
  }, [itineraryId]);

  useEffect(() => {
    if (!window.kakao?.maps || !mapRef.current) {
      return;
    }

    window.kakao.maps.load(() => {
      const kakao = window.kakao;

      if (!mapInstanceRef.current) {
        mapInstanceRef.current =
          new kakao.maps.Map(
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

      overlaysRef.current.forEach(
        (overlay) => overlay.setMap(null)
      );

      polylinesRef.current.forEach(
        (polyline) => polyline.setMap(null)
      );

      overlaysRef.current = [];
      polylinesRef.current = [];

      const bounds =
        new kakao.maps.LatLngBounds();

      let pointCount = 0;

      const drawPath = (
        points,
        color,
        weight
      ) => {
        const path = points.map((point) => {
          const position =
            new kakao.maps.LatLng(
              Number(point.latitude),
              Number(point.longitude)
            );

          bounds.extend(position);
          pointCount += 1;

          return position;
        });

        if (path.length < 2) {
          return;
        }

        const polyline =
          new kakao.maps.Polyline({
            path,
            strokeWeight: weight,
            strokeColor: color,
            strokeOpacity: 0.88,
            strokeStyle: 'solid',
          });

        polyline.setMap(map);

        polylinesRef.current.push(
          polyline
        );
      };

      const drawMarkers = (
        points,
        dayNumber,
        label,
        color
      ) => {
        points.forEach(
          (point, index) => {
            const position =
              new kakao.maps.LatLng(
                Number(point.latitude),
                Number(point.longitude)
              );

            bounds.extend(position);
            pointCount += 1;

            const marker =
              document.createElement(
                'button'
              );

            marker.type = 'button';

            marker.textContent =
              `${dayNumber}-${index + 1}`;

            marker.title =
              `${label} DAY ${dayNumber} · ` +
              `${index + 1}. ${point.title || ''}`;

            Object.assign(
              marker.style,
              {
                minWidth: '31px',
                height: '29px',
                padding: '0 5px',
                borderRadius: '100px',
                border:
                  '2px solid #1B211D',
                background: color,
                color: '#fff',
                fontSize: '11px',
                fontWeight: '800',
                cursor: 'pointer',
                boxShadow:
                  '2px 2px 0 #1B211D',
              }
            );

            const overlay =
              new kakao.maps.CustomOverlay({
                position,
                content: marker,
                yAnchor: 1,
                zIndex: 10,
              });

            overlay.setMap(map);

            overlaysRef.current.push(
              overlay
            );
          }
        );
      };

      if (currentProduct === 'stored') {
        storedDays.forEach(
          (day, dayIndex) => {
            const dayNumber = Number(
              day.day ?? dayIndex + 1
            );

            const points = (
              day.items || []
            )
              .filter(validPoint)
              .sort(
                (a, b) =>
                  Number(
                    a.sequence ?? 0
                  ) -
                  Number(
                    b.sequence ?? 0
                  )
              );

            const roadPath = (
              day.path || []
            ).filter(validPoint);

            const color =
              dayColor(dayNumber);

            if (roadPath.length >= 2) {
              drawPath(
                roadPath,
                color,
                6
              );
            }

            drawMarkers(
              points,
              dayNumber,
              '추천 패키지',
              color
            );
          }
        );
      } else {
        customRoutes.forEach(
          (route, routeIndex) => {
            const dayNumber = Number(
              route.day_number ??
                routeIndex + 1
            );

            const points = (
              route.points || []
            ).filter(validPoint);

            const roadPath = (
              route.path || []
            ).filter(validPoint);

            const color =
              dayColor(dayNumber);

            if (roadPath.length >= 2) {
              drawPath(
                roadPath,
                color,
                5
              );
            }

            drawMarkers(
              points,
              dayNumber,
              '자유일정',
              color
            );
          }
        );
      }

      if (pointCount > 0) {
        map.setBounds(bounds);

        requestAnimationFrame(() => {
          kakao.maps.event.trigger(
            map,
            'resize'
          );

          map.setBounds(bounds);
        });
      }
    });

    return () => {
      overlaysRef.current.forEach(
        (overlay) =>
          overlay.setMap(null)
      );

      polylinesRef.current.forEach(
        (polyline) =>
          polyline.setMap(null)
      );
    };
  }, [
    currentProduct,
    customRoutes,
    storedDays,
  ]);

  const visibleDayNumbers = (
    currentProduct === 'stored'
      ? storedDays.map(
          (day, index) =>
            Number(
              day.day ?? index + 1
            )
        )
      : customRoutes.map(
          (route, index) =>
            Number(
              route.day_number ??
                index + 1
            )
        )
  ).filter(Number.isFinite);

  return (
    <>
      {mode === 'compare' && (
        <div
          className={
            styles.comparisonMapTabs
          }
        >
          <button
            type="button"
            className={
              activeProduct === 'stored'
                ? styles.comparisonMapTabActive
                : ''
            }
            onClick={() =>
              setActiveProduct('stored')
            }
          >
            추천 패키지
          </button>

          <button
            type="button"
            className={
              activeProduct === 'custom'
                ? styles.comparisonMapTabActive
                : ''
            }
            onClick={() =>
              setActiveProduct('custom')
            }
          >
            자유일정
          </button>
        </div>
      )}

      <div
        className={
          styles.comparisonDayLegend
        }
      >
        {visibleDayNumbers.map((day) => (
          <span key={day}>
            <i
              style={{
                backgroundColor:
                  dayColor(day),
              }}
            />
            {day}일차
          </span>
        ))}
      </div>

      <div
        ref={mapRef}
        className={
          styles.comparisonMapCanvas
        }
      />
    </>
  );
}