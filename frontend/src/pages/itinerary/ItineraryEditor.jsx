import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import styles from './itinerary.module.css'
import cx from '../../utils/cx.js'

// 필드명은 백엔드 ItineraryDay/ItineraryItem 모델과 맞춤
// (dayNumber → day_number, thumbnail/description/itemType → thumbnail/description/item_type)
const DAYS = [
  {
    dayNumber: 1,
    date: '7/25 (목)',
    total: '129,000원',
    items: [
      { time: '09:30', itemType: 'spot', thumbnail: '🌋', title: '성산일출봉', description: '일출 명소로 유명한 대표 관광지' },
      { time: '12:00', itemType: 'spot', thumbnail: '🏖️', title: '협재해변', description: '에메랄드빛 바다 · 산책하기 좋은 해변' },
      { time: '13:30', itemType: 'restaurant', thumbnail: '🍖', title: '점심 식사 — 흑돼지 맛집', description: '현지 맛집 추천 · 흑돼지 정식' },
      { time: '15:30', itemType: 'spot', thumbnail: '🍵', title: '오설록 티뮤지엄', description: '녹차밭 산책과 티하우스 체험' },
      { time: '17:30', itemType: 'accommodation', thumbnail: '🛏️', title: '숙소 체크인', description: '제주 오션뷰 호텔' },
    ],
  },
  {
    dayNumber: 2,
    date: '7/26 (금)',
    total: '168,000원',
    items: [
      { time: '09:00', itemType: 'spot', thumbnail: '🌲', title: '사려니숲길', description: '편백나무 향 가득한 여유로운 산책로' },
      { time: '11:00', itemType: 'spot', thumbnail: '🏮', title: '동문관덕정', description: '제주 전통 시장 골목 구경' },
      { time: '12:30', itemType: 'restaurant', thumbnail: '🍖', title: '흑돼지 맛집', description: '현지인 추천 흑돼지 맛집' },
      { time: '14:30', itemType: 'spot', thumbnail: '☕', title: '카페 스누피가든', description: '사진 찍기 좋은 테마 카페 겸 정원' },
      { time: '19:00', itemType: 'restaurant', thumbnail: '🍜', title: '저녁 식사 — 물회국수', description: '제주식 시원한 물회 한 그릇' },
    ],
  },
  {
    dayNumber: 3,
    date: '7/27 (토)',
    total: '141,700원',
    items: [
      { time: '09:00', itemType: 'spot', thumbnail: '🏖️', title: '협재 해변 산책', description: '마지막 날 아침 여유로운 바다 산책' },
      { time: '11:00', itemType: 'restaurant', thumbnail: '🍲', title: '점심 식사 — 해물뚝배기', description: '떠나기 전 든든한 한 끼' },
      { time: '13:00', itemType: 'spot', thumbnail: '🎨', title: '아르떼뮤지엄', description: '몰입형 미디어아트 전시로 마무리' },
      { time: '16:00', itemType: 'custom', thumbnail: '✈️', title: '공항 이동 및 출국', description: '렌터카 반납 후 공항으로 이동' },
    ],
  },
]

export default function ItineraryEditor() {
  const [days, setDays] = useState(DAYS)
  const [activeDay, setActiveDay] = useState(1)
  const [openMenuIndex, setOpenMenuIndex] = useState(null)
  const [editingIndex, setEditingIndex] = useState(null)
  const [editDraft, setEditDraft] = useState(null)
  const [deleteIndex, setDeleteIndex] = useState(null)
  const navigate = useNavigate()
  const current = days.find((d) => d.dayNumber === activeDay)

  const toggleMenu = (i) => setOpenMenuIndex((prev) => (prev === i ? null : i))

  const startEdit = (i) => {
    setEditDraft({ ...current.items[i] })
    setEditingIndex(i)
    setOpenMenuIndex(null)
  }

  const cancelEdit = () => {
    setEditingIndex(null)
    setEditDraft(null)
  }

  const saveEdit = () => {
    setDays((prev) =>
      prev.map((d) =>
        d.dayNumber !== activeDay
          ? d
          : { ...d, items: d.items.map((item, i) => (i === editingIndex ? editDraft : item)) }
      )
    )
    setEditingIndex(null)
    setEditDraft(null)
  }

  const askDelete = (i) => {
    setDeleteIndex(i)
    setOpenMenuIndex(null)
  }

  const cancelDelete = () => setDeleteIndex(null)

  const confirmDelete = () => {
    setDays((prev) =>
      prev.map((d) =>
        d.dayNumber !== activeDay ? d : { ...d, items: d.items.filter((_, i) => i !== deleteIndex) }
      )
    )
    setDeleteIndex(null)
  }

  return (
    <div className={styles.itCol}>
      <div className={styles.itTop}>
        <div>
          <div className={styles.sectionTag}>✓ 일정 확인 및 수정</div>
          <h1>제주 2박 3일 힐링 여행</h1>
          <p>부모님과 함께 · 2024.07.25(목) – 07.27(토) · 2인 · 1인당 약 50만원</p>
        </div>
        <button className={cx(styles.btn, styles.ghost, styles.sm)}>🔄 일정 다시 생성</button>
      </div>

      <div className={styles.dayTabs}>
        {DAYS.map((d) => (
          <button
            key={d.dayNumber}
            className={cx(styles.dayTab, activeDay === d.dayNumber && styles.dayTabActive)}
            onClick={() => setActiveDay(d.dayNumber)}
          >
            DAY {d.dayNumber} <span>{d.date}</span>
          </button>
        ))}
      </div>

      <div className={styles.timeline}>
        {current.items.map((item, i) =>
          editingIndex === i ? (
            <div className={styles.tEditCard} key={i}>
              <div className={styles.tEditRow}>
                <div className={styles.tEditField}>
                  <label>시간</label>
                  <input
                    type="text"
                    value={editDraft.time}
                    onChange={(e) => setEditDraft({ ...editDraft, time: e.target.value })}
                  />
                </div>
                <div className={cx(styles.tEditField, styles.tEditFieldGrow)}>
                  <label>장소명</label>
                  <input
                    type="text"
                    value={editDraft.title}
                    onChange={(e) => setEditDraft({ ...editDraft, title: e.target.value })}
                  />
                </div>
              </div>
              <div className={styles.tEditField}>
                <label>설명</label>
                <input
                  type="text"
                  value={editDraft.description}
                  onChange={(e) => setEditDraft({ ...editDraft, description: e.target.value })}
                />
              </div>
              <div className={styles.tEditActions}>
                <button className={cx(styles.btn, styles.ghost, styles.xs)} onClick={cancelEdit}>
                  취소
                </button>
                <button className={cx(styles.btn, styles.primary, styles.xs)} onClick={saveEdit}>
                  저장
                </button>
              </div>
            </div>
          ) : (
            <div className={styles.tItem} key={i}>
              <div className={styles.tTime}>{item.time}</div>
              <div className={styles.tThumb}>{item.thumbnail}</div>
              <div className={styles.tBody}>
                <h5>{item.title}</h5>
                <p>{item.description}</p>
              </div>
              <div className={styles.tMenuWrap}>
                <button
                  className={styles.tMenu}
                  onClick={() => toggleMenu(i)}
                  aria-haspopup="true"
                  aria-expanded={openMenuIndex === i}
                >
                  ⋮
                </button>
                {openMenuIndex === i && (
                  <>
                    <div className={styles.tMenuBackdrop} onClick={() => setOpenMenuIndex(null)} />
                    <div className={styles.tMenuDropdown}>
                      <button className={styles.tMenuItem} onClick={() => startEdit(i)}>
                        ✏️ 수정
                      </button>
                      <button className={cx(styles.tMenuItem, styles.tMenuItemDanger)} onClick={() => askDelete(i)}>
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
                      <button className={cx(styles.btn, styles.ghost, styles.xs)} onClick={cancelDelete}>
                        취소
                      </button>
                      <button className={cx(styles.btn, styles.dangerBtn, styles.xs)} onClick={confirmDelete}>
                        삭제하기
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        )}
        <button className={styles.addSpot}>+ 장소 추가</button>
        <div className={styles.itTotal}>
          <div className={styles.lbl}>Day {current.dayNumber} 예상 비용</div>
          <div className={styles.val}>{current.total}</div>
        </div>
      </div>

      <div className={styles.itActions}>
        <Link to="/chat" className={cx(styles.btn, styles.ghost)}>
          이전 단계로
        </Link>
        <button className={cx(styles.btn, styles.primary)} onClick={() => navigate('/review')}>
          이 일정으로 확정하기 →
        </button>
      </div>
    </div>
  )
}
