import { Link, useNavigate, useParams } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

import styles from './review/review.module.css'
import cx from '../utils/cx.js'
import AppHeader from './review/AppHeader.jsx'
import {
  DayNav,
  DayColumns,
  useDayNav,
} from './review/ItineraryOverview.jsx'
import TripSummary from './review/TripSummary.jsx'
import {
  getItinerary,
  createShareLink,
  getSharedItinerary,
} from '../api/itinerary'

export default function ReviewPage() {
  const { id, token } = useParams()
  const navigate = useNavigate()
  const { activeDay, selectDay, dayRefs } = useDayNav()

  const [itinerary, setItinerary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showToast, setShowToast] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)

  const pdfRef = useRef(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        let data

        if (token) {
          data = await getSharedItinerary(token)
        } else {
          data = await getItinerary(id)
        }

        setItinerary(data)
      } catch (error) {
        console.error(error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [id, token])

  const handleShare = async () => {
    try {
      const data = await createShareLink(id)

      let shareUrl = data.share_url

      if (!shareUrl) {
        shareUrl = `${window.location.origin}/share/${data.share_token}`
      }

      await navigator.clipboard.writeText(shareUrl)

      setShowToast(true)

      setTimeout(() => {
        setShowToast(false)
      }, 2000)
    } catch (error) {
      console.error(error)
    }
  }

  const handlePdfDownload = async () => {
    if (!pdfRef.current || isDownloading) return

    setIsDownloading(true)

    try {
      const canvas = await html2canvas(pdfRef.current, {
        scale: 2,
        useCORS: true,
        backgroundColor: '#ffffff',
      })

      const imageData = canvas.toDataURL('image/png')

      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      })

      const pageWidth = pdf.internal.pageSize.getWidth()
      const pageHeight = pdf.internal.pageSize.getHeight()
      const margin = 10
      const imageWidth = pageWidth - margin * 2
      const imageHeight = (canvas.height * imageWidth) / canvas.width
      const printableHeight = pageHeight - margin * 2

      let position = margin
      let remainingHeight = imageHeight

      pdf.addImage(
        imageData,
        'PNG',
        margin,
        position,
        imageWidth,
        imageHeight,
      )

      remainingHeight -= printableHeight

      while (remainingHeight > 0) {
        position -= printableHeight
        pdf.addPage()

        pdf.addImage(
          imageData,
          'PNG',
          margin,
          position,
          imageWidth,
          imageHeight,
        )

        remainingHeight -= printableHeight
      }

      pdf.save(`${itinerary.title || '여행_일정'}.pdf`)
    } catch (error) {
      console.error('PDF 다운로드 실패:', error)
      alert('PDF 다운로드에 실패했습니다.')
    } finally {
      setIsDownloading(false)
    }
  }

  if (loading) {
    return <div>일정을 불러오는 중...</div>
  }

  if (!itinerary) {
    return <div>일정을 찾을 수 없습니다.</div>
  }

  return (
    <div className={styles.page}>
      <AppHeader />

      <div className={styles.wrap}>
        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 최종 일정 확인</div>
          <h1>확정 전, 마지막으로 검토해주세요</h1>
          <p>
            일정과 예상 비용을 확인하고, 이 일정으로 예약을 진행할 수
            있어요.
          </p>
        </div>

        <div className={styles.shell}>
          <DayNav
            days={itinerary.days}
            activeDay={activeDay}
            onSelect={selectDay}
          />

          <div className={styles.mainCard} ref={pdfRef}>
            <div className={styles.topRow}>
              <div>
                <h2>{itinerary.title}</h2>
                <div className={styles.sub}>{itinerary.subtitle}</div>
              </div>

              {!token && (
                <div
                  className={styles.actionRow}
                  data-html2canvas-ignore="true"
                >
                  {showToast && (
                    <div className={styles.toast}>
                      링크 복사!
                    </div>
                  )}

                  <button
                    className={cx(
                      styles.btn,
                      styles.ghost,
                      styles.sm,
                    )}
                    onClick={handleShare}
                  >
                    📤 공유하기
                  </button>

                  <button
                    className={cx(
                      styles.btn,
                      styles.ghost,
                      styles.sm,
                    )}
                    onClick={handlePdfDownload}
                    disabled={isDownloading}
                  >
                    {isDownloading
                      ? 'PDF 생성 중...'
                      : '📄 PDF 다운로드'}
                  </button>

                  <Link
                    to="/itinerary"
                    className={cx(
                      styles.btn,
                      styles.ghost,
                      styles.sm,
                    )}
                  >
                    ✏️ 일정 수정하기
                  </Link>
                </div>
              )}
            </div>

            <div className={styles.metaRow}>
              <div className={styles.metaItem}>
                📅 {itinerary.durationLabel}
              </div>

              <div className={styles.metaItem}>
                👥 {itinerary.companionCount}명
              </div>

              <div className={styles.metaItem}>
                🍃 {itinerary.style}
              </div>

              <div className={styles.metaItem}>
                💰 1인당{' '}
                {(itinerary.budgetPerPerson ?? 0).toLocaleString()}원
              </div>
            </div>

            <div className={styles.grid}>
              <DayColumns
                days={itinerary.days}
                dayRefs={dayRefs}
              />

              <TripSummary itinerary={itinerary} />
            </div>
          </div>
        </div>

        {!token && (
          <div className={styles.bottomActions}>
            <Link
              to="/itinerary"
              className={cx(styles.btn, styles.ghost)}
            >
              이전 단계로
            </Link>

            <button
              className={cx(styles.btn, styles.primary)}
              onClick={() =>
                navigate('/booking', {
                  state: {
                    itineraryId: id,
                  },
                })
              }
            >
              이 일정으로 확정하기 →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}