import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import styles from "./itinerary.module.css";
import cx from "../../utils/cx.js";

import { getItinerary } from "../../api/itinerary";
import { useItineraries } from "../../context/ItineraryContext";

export default function ItineraryEditor({
  activeDay,
  setActiveDay,
  refreshKey = 0,
}) {
  const navigate = useNavigate();
  const { id } = useParams();

  const { patch, regenerate } = useItineraries();

  const [itinerary, setItinerary] = useState(null);
  const [days, setDays] = useState([]);

  const [openMenuIndex, setOpenMenuIndex] = useState(null);
  const [deleteIndex, setDeleteIndex] = useState(null);

  const current = days.find((d) => d.dayNumber === activeDay);

  useEffect(() => {
    const fetchItinerary = async () => {
      try {
        const data = await getItinerary(id);

        setItinerary(data);
        setDays(data.days);
      } catch (err) {
        console.error(err);
      }
    };

    fetchItinerary();
  }, [id, refreshKey]);

  const toggleMenu = (i) => {
    setOpenMenuIndex((prev) => (prev === i ? null : i));
  };

  const toApiDays = (days) =>
    days.map((day) => ({
      day_number: day.dayNumber,
      date: day.date,
      items: day.items.map((item, index) => ({
        order: item.order ?? index,
        time: item.time ?? "",
        item_type: item.item_type ?? "custom",
        title: item.title,
        description: item.description ?? "",
        thumbnail: item.thumbnail ?? "",
        cost: item.cost ?? 0,
        spot: item.spot ?? null,
        restaurant: item.restaurant ?? null,
        accommodation: item.accommodation ?? null,
        latitude: item.latitude ?? null,
        longitude: item.longitude ?? null,
        memo: item.memo ?? "",
      })),
    }));

  const askDelete = (i) => {
    setDeleteIndex(i);
    setOpenMenuIndex(null);
  };

  const cancelDelete = () => {
    setDeleteIndex(null);
  };

  const confirmDelete = async () => {
    const updatedDays = days.map((d) =>
      d.dayNumber !== activeDay
        ? d
        : {
            ...d,
            items: d.items.filter((_, i) => i !== deleteIndex),
          }
    );

    try {
      const updated = await patch(itinerary.id, {
        days: toApiDays(updatedDays),
      });

      setItinerary(updated);
      setDays(updated.days);
    } catch (err) {
      console.error(err);
      alert("삭제 저장 실패");
    }

    setDeleteIndex(null);
  };

  const handleRegenerate = async () => {
    const confirmed = window.confirm(
      "일정을 다시 생성하면 지금까지 직접 수정하거나 삭제한 내용이 모두 사라지고, 같은 조건(동행자·기간·교통수단·스타일)으로 새 일정을 처음부터 만들어요.\n계속할까요?"
    );

    if (!confirmed) return;

    try {
      const data = await regenerate(itinerary.id);

      setItinerary(data);
      setDays(data.days);
    } catch (err) {
      console.error(err);
      alert("일정 재생성 실패");
    }
  };

  const handleRevise = async (message) => {
    try {
      const data = await revise(itinerary.id, message);

      setItinerary(data);
      setDays(data.days);
    } catch (err) {
      console.error(err);
      alert("일정 수정 실패");
    }
  };

  if (!itinerary || !current) {
    return <div>일정을 불러오는 중...</div>;
  }
    return (
    <div className={styles.itCol}>
      <div className={styles.itTop}>
        <div>
          <div className={styles.sectionTag}>✓ 일정 확인 및 수정</div>
          <h1>{itinerary.title}</h1>
          <p>
            {itinerary.subtitle} · {itinerary.startDate} ~ {itinerary.endDate}
          </p>
        </div>

        <button
          className={cx(styles.btn, styles.ghost, styles.sm)}
          onClick={handleRegenerate}
        >
          🔄 일정 다시 생성
        </button>
      </div>

      <div className={styles.dayTabs}>
        {days.map((day) => (
          <button
            key={day.dayNumber}
            className={cx(
              styles.dayTab,
              activeDay === day.dayNumber && styles.dayTabActive
            )}
            onClick={() => setActiveDay(day.dayNumber)}
          >
            DAY {day.dayNumber}
            <span>{day.date}</span>
          </button>
        ))}
      </div>

      <div className={styles.timeline}>
        {current.items.map((item, i) => (
          <div className={styles.tItem} key={item.id ?? i}>
            <div className={styles.tTime}>{item.time}</div>

            <div className={styles.tThumb}>
              {item.thumbnail ? (
                <img
                  src={item.thumbnail}
                  alt={item.title}
                  className={styles.thumb}
                />
              ) : (
                "📍"
              )}
            </div>

            <div className={styles.tBody}>
              <h5>{item.title}</h5>
              <p>{item.description}</p>
            </div>

            <div className={styles.tMenuWrap}>
              <button
                className={styles.tMenu}
                onClick={() => toggleMenu(i)}
              >
                ⋮
              </button>

              {openMenuIndex === i && (
                <>
                  <div
                    className={styles.tMenuBackdrop}
                    onClick={() => setOpenMenuIndex(null)}
                  />

                  <div className={styles.tMenuDropdown}>
                    <button
                      className={cx(
                        styles.tMenuItem,
                        styles.tMenuItemDanger
                      )}
                      onClick={() => askDelete(i)}
                    >
                      🗑️ 삭제
                    </button>
                  </div>
                </>
              )}
            </div>

            {deleteIndex === i && (
              <div className={styles.tDeleteConfirmOverlay}>
                <div className={styles.tDeleteConfirm}>
                  <p>
                    <b>{item.title}</b> 일정을 삭제할까요?
                  </p>

                  <div className={styles.tEditActions}>
                    <button
                      className={cx(
                        styles.btn,
                        styles.ghost,
                        styles.xs
                      )}
                      onClick={cancelDelete}
                    >
                      취소
                    </button>

                    <button
                      className={cx(
                        styles.btn,
                        styles.dangerBtn,
                        styles.xs
                      )}
                      onClick={confirmDelete}
                    >
                      삭제하기
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}

        <div className={styles.itTotal}>
          <div className={styles.lbl}>
            Day {current.dayNumber} 예상 비용
          </div>

          <div className={styles.val}>
            {current.total}
          </div>
        </div>
      </div>

      <div className={styles.itActions}>
        <Link
          to="/chat"
          className={cx(styles.btn, styles.ghost)}
        >
          이전 단계로
        </Link>

        <button
          className={cx(styles.btn, styles.primary)}
          onClick={() => navigate(`/review/${itinerary.id}`)}
        >
          이 일정으로 확정하기 →
        </button>
      </div>
    </div>
  );
}