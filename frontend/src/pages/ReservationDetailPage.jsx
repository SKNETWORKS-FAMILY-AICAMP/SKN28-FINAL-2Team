import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

import { getItinerary, createShareLink } from '../api/itinerary'
import { getPackageDetail, getPackages } from '../api/packageApi'
import { cancelReservation, getReservation } from '../api/reservationApi'
import AppHeader from './review/AppHeader.jsx'
import ReservationRouteMap from './reservation/ReservationRouteMap.jsx'
import styles from './reservation/reservationDetail.module.css'

const won = (value) => `${Number(value || 0).toLocaleString('ko-KR')}원`

const itemTypeLabel = (type) => {
  if (type === 'restaurant') return '음식점'
  if (type === 'hotel' || type === 'accommodation') return '숙소'
  if (type === 'activity') return '액티비티'
  return '관광지'
}

const packageDays = (course = []) =>
  course.map((day, index) => ({
    dayNumber: Number(day.day ?? index + 1),
    date: '',
    items: (day.items || []).map((item) => ({
      ...item,
      item_type: item.item_type || 'tourism',
    })),
  }))

const shareText = (title, days) => {
  const schedule = days
    .map((day) => {
      const items = (day.items || [])
        .map((item, index) => `${index + 1}. ${item.title}`)
        .join('\n')
      return `[${day.dayNumber}일차]\n${items}`
    })
    .join('\n\n')

  return `${title}\n\n${schedule}`
}

export default function ReservationDetailPage() {
  const { id } = useParams()
  const pdfRef = useRef(null)
  const [reservation, setReservation] = useState(null)
  const [itinerary, setItinerary] = useState(null)
  const [packageDetails, setPackageDetails] = useState({})
  const [activeItemId, setActiveItemId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [downloading, setDownloading] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError('')

      try {
        const reservationData = await getReservation(id)
        if (cancelled) return
        setReservation(reservationData)
        setActiveItemId(reservationData.items?.[0]?.id ?? null)

        const [itineraryResult, packageResults] = await Promise.all([
          reservationData.itinerary
            ? getItinerary(reservationData.itinerary).catch(() => null)
            : Promise.resolve(null),
          (async () => {
            const storedItems = (reservationData.items || []).filter(
              (item) =>
                item.product_type !== 'custom_itinerary' &&
                !String(item.package_id || '').toUpperCase().startsWith('CUSTOM-'),
            )
            const needsPackageLookup = storedItems.some((item) => !item.package_db_id)
            const packageResponse = needsPackageLookup
              ? await getPackages().catch(() => [])
              : []
            const packageList = Array.isArray(packageResponse)
              ? packageResponse
              : packageResponse?.results || []

            return Promise.all(
              storedItems.map(async (item) => {
                const resolvedId = item.package_db_id || packageList.find(
                  (pkg) => pkg.package_id === item.package_id,
                )?.id
                return [
                  item.id,
                  resolvedId ? await getPackageDetail(resolvedId).catch(() => null) : null,
                ]
              }),
            )
          })(),
        ])

        if (cancelled) return
        setItinerary(itineraryResult)
        setPackageDetails(Object.fromEntries(packageResults))
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError.message || '예약 상세 정보를 불러오지 못했습니다.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [id])

  const activeItem = useMemo(
    () => reservation?.items?.find((item) => item.id === activeItemId) ?? reservation?.items?.[0],
    [activeItemId, reservation],
  )

  const isCustom =
    activeItem?.product_type === 'custom_itinerary' ||
    String(activeItem?.package_id || '').toUpperCase().startsWith('CUSTOM-')
  const packageDetail = activeItem ? packageDetails[activeItem.id] : null
  const days = isCustom
    ? (itinerary?.days || [])
    : packageDays(activeItem?.schedule?.length ? activeItem.schedule : packageDetail?.course)
  const title = activeItem?.name || packageDetail?.name || itinerary?.title || '예약한 여행 일정'
  const description = isCustom
    ? '사용자가 확정한 일정으로 구성된 자유패키지입니다.'
    : packageDetail?.description || '여행사에서 구성한 제주 여행 패키지입니다.'

  const showToast = (message) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 2200)
  }

  const handleShare = async () => {
    try {
      let text = shareText(title, days)
      let url = ''

      if (isCustom && itinerary?.id) {
        const data = await createShareLink(itinerary.id)
        url = data.share_url || `${window.location.origin}/share/${data.share_token}`
      }

      if (navigator.share) {
        await navigator.share({ title, text, ...(url ? { url } : {}) })
        showToast('공유 화면을 열었습니다.')
      } else {
        await navigator.clipboard.writeText(url || text)
        showToast(url ? '공유 링크를 복사했습니다.' : '일정 내용을 복사했습니다.')
      }
    } catch (shareError) {
      if (shareError?.name !== 'AbortError') {
        console.error('일정 공유 실패:', shareError)
        showToast('공유하지 못했습니다.')
      }
    }
  }

  const handlePdf = async () => {
    if (!pdfRef.current || downloading) return
    setDownloading(true)

    try {
      const canvas = await html2canvas(pdfRef.current, {
        scale: 2,
        useCORS: true,
        backgroundColor: '#ffffff',
      })
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
      const margin = 10
      const pageWidth = pdf.internal.pageSize.getWidth()
      const pageHeight = pdf.internal.pageSize.getHeight()
      const imageWidth = pageWidth - margin * 2
      const imageHeight = (canvas.height * imageWidth) / canvas.width
      const printableHeight = pageHeight - margin * 2
      const imageData = canvas.toDataURL('image/png')
      let position = margin
      let remaining = imageHeight

      pdf.addImage(imageData, 'PNG', margin, position, imageWidth, imageHeight)
      remaining -= printableHeight

      while (remaining > 0) {
        position -= printableHeight
        pdf.addPage()
        pdf.addImage(imageData, 'PNG', margin, position, imageWidth, imageHeight)
        remaining -= printableHeight
      }

      pdf.save(`${title}.pdf`)
    } catch (pdfError) {
      console.error('PDF 다운로드 실패:', pdfError)
      showToast('PDF를 만들지 못했습니다.')
    } finally {
      setDownloading(false)
    }
  }

  const handleCancel = async () => {
    if (!window.confirm('이 예약을 취소할까요? 취소 후에는 되돌릴 수 없습니다.')) return
    setCancelling(true)
    try {
      const updated = await cancelReservation(reservation.id)
      setReservation(updated)
    } catch (cancelError) {
      showToast(cancelError.message || '예약을 취소하지 못했습니다.')
    } finally {
      setCancelling(false)
    }
  }

  if (loading) return <div className={styles.message}>예약 일정을 불러오는 중입니다.</div>
  if (error || !reservation) return <div className={`${styles.message} ${styles.error}`}>{error || '예약을 찾을 수 없습니다.'}</div>

  return (
    <div className={styles.page}>
      <AppHeader />
      <main className={styles.wrap}>
        <Link className={styles.backLink} to="/my/reservations">← 예약 내역으로 돌아가기</Link>

        <header className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 예약 일정 확인</div>
          <h1>예약한 여행 일정을 확인해보세요</h1>
          <p>예약한 코스를 확인하고 PDF로 저장하거나 공유할 수 있어요.</p>
        </header>

        {reservation.items.length > 1 && (
          <div className={styles.productTabs}>
            {reservation.items.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`${styles.productTab} ${item.id === activeItem?.id ? styles.productTabActive : ''}`}
                onClick={() => setActiveItemId(item.id)}
              >
                {item.name}
              </button>
            ))}
          </div>
        )}

        <article className={styles.card} ref={pdfRef}>
          <div className={styles.topRow}>
            <div>
              <span className={styles.productType}>{isCustom ? '자유패키지' : '여행사 패키지'}</span>
              <h2>{title}</h2>
              <p className={styles.sub}>{description}</p>
            </div>
            <strong className={styles.price}>{won(activeItem?.price)} <small>/ 1인</small></strong>
          </div>

          <div className={styles.actions} data-html2canvas-ignore="true">
            {toast && <div className={styles.toast}>{toast}</div>}
            <button type="button" className={styles.button} onClick={handleShare}>📤 공유하기</button>
            <button type="button" className={styles.button} onClick={handlePdf} disabled={downloading}>
              {downloading ? 'PDF 생성 중...' : '📄 PDF 다운로드'}
            </button>
          </div>

          <div className={styles.metaRow}>
            <span className={styles.metaItem}>🧾 예약 #{reservation.id}</span>
            <span className={styles.metaItem}>📅 {new Date(reservation.created_at).toLocaleDateString('ko-KR')}</span>
            <span className={styles.metaItem}>👤 수량 {activeItem?.quantity || 1}명</span>
            <span className={styles.metaItem}>✓ {reservation.status_display}</span>
          </div>

          <div className={styles.contentGrid}>
            <div className={styles.days}>
              {days.length > 0 ? days.map((day, dayIndex) => (
                <section className={styles.day} key={day.dayNumber ?? dayIndex}>
                  <div className={styles.dayHead}>
                    DAY {day.dayNumber ?? dayIndex + 1}
                    {day.date && <span>{day.date}</span>}
                  </div>
                  {(day.items || []).map((item, itemIndex) => (
                    <div className={styles.stop} key={`${item.id ?? item.content_id ?? item.title}-${itemIndex}`}>
                      <div className={styles.thumb}>
                        {item.thumbnail ? <img src={item.thumbnail} alt="" /> : '📍'}
                      </div>
                      <div>
                        <strong>{item.title}</strong>
                        <p>
                          {itemTypeLabel(item.item_type)}
                          {item.stay_minutes ? ` · ${item.stay_minutes}분` : ''}
                        </p>
                        {item.description && <p>{item.description}</p>}
                      </div>
                    </div>
                  ))}
                </section>
              )) : <p className={styles.sub}>표시할 상세 일정이 없습니다.</p>}
            </div>

            <aside className={styles.summary}>
              <h3>여행 동선</h3>
              <ReservationRouteMap days={days} />
              <div className={styles.summaryInfo}>
                <div><span>상품 유형</span><strong>{isCustom ? '자유패키지' : '여행사 패키지'}</strong></div>
                <div><span>결제 금액</span><strong>{won(activeItem?.price * (activeItem?.quantity || 1))}</strong></div>
                <div><span>결제 수단</span><strong>{reservation.payment_method}</strong></div>
              </div>
              {reservation.status === 'cancelled' ? (
                <div className={styles.cancelled}>취소된 예약입니다.</div>
              ) : (
                <button type="button" className={styles.cancelButton} onClick={handleCancel} disabled={cancelling} data-html2canvas-ignore="true">
                  {cancelling ? '취소 처리 중...' : '예약 취소'}
                </button>
              )}
            </aside>
          </div>
        </article>
      </main>
    </div>
  )
}
