import { useEffect, useRef, useState } from 'react';

import { getRoadRoute } from '../../api/itinerary';
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
  storedPackageId = null,
  storedDays = [],
  storedHotel = null,
  customHotel = null,
  mode = 'compare',
  selectedProduct = 'stored',
}) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const overlaysRef = useRef([]);
  const polylinesRef = useRef([]);

  // 실제 도로 경로 데이터
  const [customRoutes, setCustomRoutes] = useState([]);
  const [storedRoutes, setStoredRoutes] = useState([]);

  // 이미 조회한 경로를 다시 요청하지 않기 위한 key
  const loadedCustomKeyRef = useRef(null);
  const loadedStoredKeyRef = useRef(null);

  // 컴포넌트가 사라진 뒤 state 변경 방지
  const mountedRef = useRef(true);
  
  const [activeProduct, setActiveProduct] = useState(
    mode === 'custom'
      ? 'custom'
      : mode === 'stored' || storedDays.length > 0 || validPoint(storedHotel)
        ? 'stored'
        : 'custom'
  );

  const currentProduct =
    mode === 'stored'
      ? 'stored'
      : mode === 'custom'
        ? 'custom'
        : selectedProduct;

  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
    };
  }, []);

  /*
   * 실제 도로 경로 조회
   *
   * - 현재 화면에서 필요한 상품만 조회
   * - 동일 상품은 한 번 조회한 뒤 재사용
   * - 탭 변경/지도 재렌더링으로 재호출하지 않음
   */
  useEffect(() => {
    if (!itineraryId) {
      return;
    }

    const loadStoredRoute = async () => {
      if (!storedPackageId) {
        return;
      }

      const key =
        `${itineraryId}:package:${storedPackageId}`;

      if (loadedStoredKeyRef.current === key) {
        return;
      }

      loadedStoredKeyRef.current = key;

      try {
        const routes = await getRoadRoute(
          itineraryId,
          storedPackageId
        );

        if (!mountedRef.current) {
          return;
        }

        setStoredRoutes(routes);
      } catch (error) {
        loadedStoredKeyRef.current = null;

        console.error(
          '추천 패키지 실제 도로 경로 조회 실패:',
          error
        );
      }
    };

    const loadCustomRoute = async () => {
      const key = `${itineraryId}:custom`;

      if (loadedCustomKeyRef.current === key) {
        return;
      }

      loadedCustomKeyRef.current = key;

      try {
        const routes = await getRoadRoute(
          itineraryId
        );

        if (!mountedRef.current) {
          return;
        }

        setCustomRoutes(routes);
      } catch (error) {
        loadedCustomKeyRef.current = null;

        console.error(
          '자유일정 실제 도로 경로 조회 실패:',
          error
        );
      }
    };

    if (currentProduct === 'stored') {
      loadStoredRoute();
    } else {
      loadCustomRoute();
    }
  }, [
    currentProduct,
    itineraryId,
    storedPackageId,
  ]);

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

      const drawHotelMarker = (hotel, label) => {
        if (!validPoint(hotel)) return;

        const position = new kakao.maps.LatLng(
          Number(hotel.latitude),
          Number(hotel.longitude)
        );

        bounds.extend(position);
        pointCount += 1;

        const marker = document.createElement('button');
        marker.type = 'button';
        marker.textContent = '🛏';
        marker.title = `${label} 숙소 · ${hotel.title || '숙소'}`;

        Object.assign(marker.style, {
          width: '34px',
          height: '34px',
          padding: '0',
          borderRadius: '10px',
          border: '2px solid #1B211D',
          background: '#FFF7DD',
          color: '#1B211D',
          fontSize: '17px',
          cursor: 'pointer',
          boxShadow: '2px 2px 0 #1B211D',
        });

        const overlay = new kakao.maps.CustomOverlay({
          position,
          content: marker,
          yAnchor: 1,
          zIndex: 12,
        });

        overlay.setMap(map);
        overlaysRef.current.push(overlay);
      };

      if (currentProduct === 'stored') {
        const routeByDay = new Map(
          storedRoutes.map((route, index) => [
            Number(
              route.day_number ??
                index + 1
            ),
            route,
          ])
        );

        storedDays.forEach(
          (day, dayIndex) => {
            const dayNumber = Number(
              day.day ??
                day.dayNumber ??
                dayIndex + 1
            );

            const points = (
              day.items || []
            )
              .filter(validPoint)
              .sort(
                (a, b) =>
                  Number(
                    a.sequence ??
                      a.order ??
                      0
                  ) -
                  Number(
                    b.sequence ??
                      b.order ??
                      0
                  )
              );

            const route =
              routeByDay.get(dayNumber);

            const roadPath = (
              route?.path || []
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
        drawHotelMarker(storedHotel, '추천 패키지');
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
        drawHotelMarker(customHotel, '자유일정');
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
    storedRoutes,
    customHotel,
    storedDays,
    storedHotel,
  ]);

  const visibleDayNumbers = (
    currentProduct === 'stored'
      ? storedDays.map(
          (day, index) =>
            Number(
              day.day ??
                day.dayNumber ??
                index + 1
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
        {validPoint(currentProduct === 'stored' ? storedHotel : customHotel) && (
          <span>
            <i style={{ backgroundColor: '#FFF7DD', border: '1px solid #1B211D' }} />
            숙소 🛏
          </span>
        )}
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
