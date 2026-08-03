import { Link } from "react-router-dom";
import styles from "./account/account.module.css";
import cx from "../utils/cx.js";
import AccountHeader from "./account/AccountHeader.jsx";
import AccountTabs from "./account/AccountTabs.jsx";
import { useItineraries } from "../context/ItineraryContext.jsx";

const won = (n) => Number(n ?? 0).toLocaleString("ko-KR") + "원";

export default function MyItinerariesPage() {
  const { itineraries, loading, removeItinerary } = useItineraries();

  if (loading) {
    return <div>일정을 불러오는 중...</div>;
  }

  const handleDelete = async (e, id) => {
    e.preventDefault();
    e.stopPropagation();

    if (!window.confirm("정말 삭제하시겠습니까?")) return;

    try {
      await removeItinerary(id);
      alert("일정이 삭제되었습니다.");
    } catch (err) {
      console.error(err);
      alert("삭제에 실패했습니다.");
    }
  };


  return (
    <div className={styles.page}>
      <AccountHeader />

      <div className={styles.wrap}>
        <AccountTabs active="/my/itineraries" />

        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 내 일정</div>

          <h1>저장한 여행 일정</h1>

          <p>
            지금까지 만든 일정을 다시 확인하고 이어서 편집할 수 있어요.
          </p>
        </div>

        <div className={styles.card}>
          {itineraries.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.icon}>🗓️</div>

              <h4>아직 저장한 일정이 없어요</h4>

              <p>AI와 대화하며 첫 여행 일정을 만들어보세요.</p>

              <Link
                to="/chat"
                className={cx(styles.btn, styles.primary)}
              >
                일정 만들러 가기 →
              </Link>
            </div>
          ) : (
            itineraries.map((it) => (
              <div className={styles.listItem} key={it.id}>
                <Link
                  to={`/review/${it.id}`}
                  style={{
                    flex: 1,
                    display: "flex",
                    textDecoration: "none",
                    color: "inherit",
                  }}
                >
                  <div className={styles.listThumb}>🌴</div>

                  <div className={styles.listInfo}>
                    <h5>{it.title}</h5>

                    <p>
                      {it.subtitle} · {it.startDate} ~ {it.endDate} ·{" "}
                      {it.durationLabel} · {it.companionCount}명
                    </p>

                    <span
                      className={cx(
                        styles.badge,
                        it.status === "confirmed"
                          ? styles.badgeConfirmed
                          : styles.badgeDraft
                      )}
                    >
                      {it.statusDisplay}
                    </span>
                  </div>

                  <div className={styles.listMeta}>
                    <div className={styles.price}>
                      {won(it.totalCost)}
                    </div>

                    <div className={styles.sub}>예상 비용</div>
                  </div>
                </Link>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    marginLeft: "16px",
                  }}
                >

                  <button
                    type="button"
                    className={styles.btn}
                    onClick={(e) => handleDelete(e, it.id)}
                  >
                    삭제
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}