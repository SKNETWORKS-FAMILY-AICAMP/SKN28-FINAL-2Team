import { useEffect, useRef, useState } from "react";
import { getRoute } from "../../api/itinerary";
import styles from "./review.module.css";


export default function TripSummary({ itinerary }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);

  const markersRef = useRef([]);
  const polylinesRef = useRef([]);
  const labelsRef = useRef([]);

  const openedLabelRef = useRef(null);

  const [routes, setRoutes] = useState([]);
  const [activeDay, setActiveDay] = useState(null);


  // -------------------------------------------------
  // 경로 데이터 조회
  // -------------------------------------------------
  useEffect(() => {
    const loadRoute = async () => {
      if (!itinerary?.id) return;

      try {
        const route = await getRoute(itinerary.id);

        setRoutes(route);

        if (route.length > 0) {
          setActiveDay(route[0].day_number);
        }
      } catch (error) {
        console.error(
          "여행 경로 조회 실패:",
          error
        );
      }
    };

    loadRoute();
  }, [itinerary?.id]);


  // -------------------------------------------------
  // 선택한 DAY 지도 표시
  // -------------------------------------------------
  useEffect(() => {
    if (!routes.length || activeDay === null) return;

    if (
      !window.kakao?.maps ||
      !mapRef.current
    ) {
      return;
    }

    window.kakao.maps.load(() => {
      const kakao = window.kakao;

      // 지도는 한 번만 생성
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


      // -------------------------------------------------
      // 기존 마커 제거
      // -------------------------------------------------
      markersRef.current.forEach(
        (marker) => {
          marker.setMap(null);
        }
      );

      markersRef.current = [];


      // -------------------------------------------------
      // 기존 경로선 제거
      // -------------------------------------------------
      polylinesRef.current.forEach(
        (polyline) => {
          polyline.setMap(null);
        }
      );

      polylinesRef.current = [];


      // -------------------------------------------------
      // 기존 장소명 제거
      // -------------------------------------------------
      labelsRef.current.forEach(
        (label) => {
          label.setMap(null);
        }
      );

      labelsRef.current = [];
      openedLabelRef.current = null;


      // -------------------------------------------------
      // 현재 선택 DAY
      // -------------------------------------------------
      const activeRoute = routes.find(
        (day) =>
          Number(day.day_number) ===
          Number(activeDay)
      );

      if (!activeRoute) return;


      // -------------------------------------------------
      // OR-Tools 방문 순서 기준 정렬
      // -------------------------------------------------
      const sortedPoints = [
        ...(activeRoute.points ?? []),
      ].sort(
        (a, b) =>
          Number(a.order) -
          Number(b.order)
      );


      const bounds =
        new kakao.maps.LatLngBounds();

      let hasPoint = false;


      // -------------------------------------------------
      // Kakao 실제 자동차 도로 경로
      // -------------------------------------------------
      const roadPath = (
        activeRoute.path ?? []
      )
        .map((point) => {
          const latitude = Number(
            point.latitude
          );

          const longitude = Number(
            point.longitude
          );

          if (
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude)
          ) {
            return null;
          }

          return new kakao.maps.LatLng(
            latitude,
            longitude
          );
        })
        .filter(Boolean);


      // -------------------------------------------------
      // 실제 도로 경로선
      // -------------------------------------------------
      if (roadPath.length >= 2) {
        const polyline =
          new kakao.maps.Polyline({
            path: roadPath,
            strokeWeight: 5,
            strokeColor: "#2E9E62",
            strokeOpacity: 0.9,
            strokeStyle: "solid",
          });

        polyline.setMap(map);

        polylinesRef.current.push(
          polyline
        );
      }


      // -------------------------------------------------
      // 순서 번호 마커
      // -------------------------------------------------
      sortedPoints.forEach((point) => {
        const latitude = Number(
          point.latitude
        );

        const longitude = Number(
          point.longitude
        );

        if (
          !Number.isFinite(latitude) ||
          !Number.isFinite(longitude)
        ) {
          return;
        }

        const position =
          new kakao.maps.LatLng(
            latitude,
            longitude
          );

        bounds.extend(position);
        hasPoint = true;


        // ---------------------------------------------
        // 번호 버튼
        // ---------------------------------------------
        const markerContent =
          document.createElement("button");

        markerContent.type = "button";

        // OR-Tools에서 저장된 실제 순서
        markerContent.textContent =
          String(point.order);

        markerContent.title =
          point.title;

        Object.assign(
          markerContent.style,
          {
            width: "32px",
            height: "32px",
            borderRadius: "50%",
            border:
              "2px solid #1B211D",
            background: "#2E9E62",
            color: "#FFFFFF",
            fontSize: "13px",
            fontWeight: "800",
            cursor: "pointer",
            boxShadow:
              "2px 2px 0 #1B211D",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }
        );


        const marker =
          new kakao.maps.CustomOverlay({
            position,
            content: markerContent,
            yAnchor: 1,
            zIndex: 10,
          });

        marker.setMap(map);

        markersRef.current.push(
          marker
        );


        // ---------------------------------------------
        // 장소명 박스
        // ---------------------------------------------
        const labelContent =
          document.createElement("div");

        labelContent.textContent =
          `${point.order}. ${point.title}`;

        Object.assign(
          labelContent.style,
          {
            minWidth: "120px",
            maxWidth: "220px",
            padding: "8px 10px",
            border:
              "1.5px solid #1B211D",
            borderRadius: "8px",
            background: "#FFFFFF",
            color: "#1B211D",
            fontSize: "12px",
            fontWeight: "700",
            lineHeight: "1.4",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            boxShadow:
              "2px 2px 0 rgba(27, 33, 29, 0.2)",
            pointerEvents: "none",
          }
        );


        const labelOverlay =
          new kakao.maps.CustomOverlay({
            position,
            content: labelContent,
            xAnchor: 0.5,
            yAnchor: 1.8,
            zIndex: 100,
          });

        labelsRef.current.push(
          labelOverlay
        );


        // ---------------------------------------------
        // 번호 클릭 → 장소명 열기/닫기
        // ---------------------------------------------
        markerContent.addEventListener(
          "click",
          () => {
            // 같은 번호 다시 클릭
            if (
              openedLabelRef.current ===
              labelOverlay
            ) {
              labelOverlay.setMap(null);

              openedLabelRef.current =
                null;

              return;
            }

            // 이전 장소명 닫기
            if (
              openedLabelRef.current
            ) {
              openedLabelRef.current.setMap(
                null
              );
            }

            // 새 장소명 열기
            labelOverlay.setMap(map);

            openedLabelRef.current =
              labelOverlay;
          }
        );
      });


      // -------------------------------------------------
      // 선택 DAY 전체 장소가 보이도록 조정
      // -------------------------------------------------
      if (hasPoint) {
        map.setBounds(bounds);

        requestAnimationFrame(() => {
          kakao.maps.event.trigger(
            map,
            "resize"
          );

          map.setBounds(bounds);
        });
      }
    });


    return () => {
      markersRef.current.forEach(
        (marker) => {
          marker.setMap(null);
        }
      );

      polylinesRef.current.forEach(
        (polyline) => {
          polyline.setMap(null);
        }
      );

      labelsRef.current.forEach(
        (label) => {
          label.setMap(null);
        }
      );

      markersRef.current = [];
      polylinesRef.current = [];
      labelsRef.current = [];

      openedLabelRef.current = null;
    };
  }, [routes, activeDay]);


  return (
    <div className={styles.summary}>
      <h4>여행 요약</h4>


      {/* DAY 선택 */}
      <div className={styles.dayButtons}>
        {routes.map((day) => {
          const isActive =
            Number(activeDay) ===
            Number(day.day_number);

          return (
            <button
              key={day.day_number}
              type="button"
              className={
                isActive
                  ? styles.dayButtonActive
                  : styles.dayButton
              }
              onClick={() =>
                setActiveDay(
                  day.day_number
                )
              }
            >
              DAY {day.day_number}
            </button>
          );
        })}
      </div>


      {/* 지도 */}
      <div
        ref={mapRef}
        className={styles.mapPanel}
      />


      <div className={styles.summaryLabel}>
        여행 기간
      </div>

      <div className={styles.summaryRow}>
        <span className={styles.v}>
          {itinerary.startDate}
          {" ~ "}
          {itinerary.endDate}
          {" · "}
          {itinerary.durationLabel}
        </span>
      </div>
    </div>
  );
}
