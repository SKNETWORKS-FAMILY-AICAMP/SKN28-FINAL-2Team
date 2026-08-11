import { Link, useNavigate, useParams } from 'react-router-dom';
import styles from './review/review.module.css';
import cx from '../utils/cx.js';
import AppHeader from './review/AppHeader.jsx';
import { DayColumns } from './review/ItineraryOverview.jsx';
import TripSummary from './review/TripSummary.jsx';
import ComparisonRouteMap from './review/ComparisonRouteMap.jsx';
import { useCart } from '../context/CartContext.jsx';
import { getPackageDetail } from '../api/packageApi.js';

import { useEffect, useRef, useState } from 'react';

import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

import {
  createShareLink,
  getItinerary,
  getPackageRecommendations,
  getSharedItinerary,
} from '../api/itinerary';


const formatPrice = (value) =>
  `${Number(value || 0).toLocaleString('ko-KR')}원`;

const itemTypeLabel = (itemType) => {
  if (itemType === 'restaurant') return '음식점';
  if (itemType === 'hotel' || itemType === 'accommodation') return '숙소';
  if (itemType === 'activity') return '액티비티';
  return '관광지';
};

function ComparisonDays({ days, custom = false }) {
  return (
    <div className={styles.comparisonDays}>
      {(days || []).map((day, dayIndex) => (
        <section
          className={styles.comparisonDay}
          key={day.day ?? day.dayNumber ?? dayIndex}
        >
          <div className={styles.comparisonDayHead}>
            DAY {day.day ?? day.dayNumber ?? dayIndex + 1}
          </div>

          <ol>
            {(day.items || []).map((item, itemIndex) => (
              <li key={`${item.content_id ?? item.id ?? item.title}-${itemIndex}`}>
                <span>{itemIndex + 1}</span>
                <div>
                  <strong>{item.title}</strong>
                  <p>
                    {itemTypeLabel(item.item_type)}
                    {!custom && item.stay_minutes
                      ? ` · ${item.stay_minutes}분`
                      : ''}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}


export default function ReviewPage() {
  const { id, token } = useParams();
  const navigate = useNavigate();
  const { addToCart, addCustomToCart, openCart } = useCart();

  const [itinerary, setItinerary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showToast, setShowToast] = useState(false);
  const [packageComparison, setPackageComparison] = useState(null);
  const [packageLoading, setPackageLoading] = useState(false);
  const [packageError, setPackageError] = useState('');
  const [selectedProduct, setSelectedProduct] = useState('stored');
  const [addingToCart, setAddingToCart] = useState(false);

  const pdfRef = useRef(null);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        let data;

        if (token) {
          data = await getSharedItinerary(token);
        } else {
          data = await getItinerary(id);
        }

        setItinerary(data);

        if (!token && data.status === 'confirmed') {
          setPackageLoading(true);
          setPackageError('');

          try {
            const comparison = await getPackageRecommendations(id, 1);
            setPackageComparison(comparison);
          } catch (error) {
            setPackageError(
              error.response?.data?.detail ??
                '패키지 정보를 불러오지 못했습니다.'
            );
          } finally {
            setPackageLoading(false);
          }
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id, token]);

  const handleBooking = async () => {
    const storedPackage = packageComparison?.stored_package;
    const customPackage = packageComparison?.custom_package;

    if (selectedProduct === 'stored') {
      if (!storedPackage?.id) return;

      let packageDetail = null;
      try {
        packageDetail = await getPackageDetail(storedPackage.id);
      } catch (error) {
        console.error('패키지 상세 이미지 조회 실패:', error);
      }

      navigate('/booking', {
        state: {
          bookingSource: 'package',
          itineraryId: itinerary.id,
          packageIds: [storedPackage.id],
          packages: [
            {
              id: storedPackage.id,
              packageId: storedPackage.package_id,
              name: storedPackage.title,
              description: storedPackage.summary || storedPackage.reason || '',
              price: storedPackage.estimated_price,
              thumbnailUrl: packageDetail?.thumbnail_url || '',
              thumbnail: '✈️',
            },
          ],
        },
      });
      return;
    }

    if (!customPackage) return;

    navigate('/booking', {
      state: {
        bookingSource: 'custom-itinerary',
        itineraryId: itinerary.id,
        packages: [
          {
            id: `custom-${itinerary.id}`,
            name: itinerary.title || '내가 확정한 자유패키지',
            description: '확정한 일정 그대로 예약하는 자유일정 상품입니다.',
            price: customPackage.price_per_person,
            thumbnail: '🧭',
            isCustom: true,
          },
        ],
      },
    });
  };

  const handleAddToCart = async () => {
    const storedPackage = packageComparison?.stored_package;
    const customPackage = packageComparison?.custom_package;

    setAddingToCart(true);
    try {
      if (selectedProduct === 'stored') {
        if (!storedPackage?.id) return;
        await addToCart(storedPackage.id, { itineraryId: itinerary.id });
      } else {
        if (!customPackage) return;
        await addCustomToCart(itinerary.id);
      }
      openCart();
    } catch (error) {
      alert(error.message || '장바구니에 상품을 담지 못했습니다.');
    } finally {
      setAddingToCart(false);
    }
  };

  const handleShare = async () => {
    try {
      const data = await createShareLink(id);

      let shareUrl = data.share_url;

      if (!shareUrl) {
        shareUrl = `${window.location.origin}/share/${data.share_token}`;
      }

      await navigator.clipboard.writeText(shareUrl);

      setShowToast(true);

      setTimeout(() => {
        setShowToast(false);
      }, 2000);
    } catch (err) {
      console.error(err);
    }
  };

  const handlePdfDownload = async () => {
    if (!pdfRef.current || isDownloading) return;

    setIsDownloading(true);

    try {
      const canvas = await html2canvas(pdfRef.current, {
        scale: 2,
        useCORS: true,
        backgroundColor: '#ffffff',
      });

      const imageData = canvas.toDataURL('image/png');

      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      });

      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();

      const margin = 10;

      const imageWidth = pageWidth - margin * 2;

      const imageHeight =
        (canvas.height * imageWidth) / canvas.width;

      const printableHeight = pageHeight - margin * 2;

      let position = margin;
      let remainingHeight = imageHeight;

      pdf.addImage(
        imageData,
        'PNG',
        margin,
        position,
        imageWidth,
        imageHeight
      );

      remainingHeight -= printableHeight;

      while (remainingHeight > 0) {
        position -= printableHeight;

        pdf.addPage();

        pdf.addImage(
          imageData,
          'PNG',
          margin,
          position,
          imageWidth,
          imageHeight
        );

        remainingHeight -= printableHeight;
      }

      pdf.save(`${itinerary.title || '여행_일정'}.pdf`);
    } catch (error) {
      console.error('PDF 다운로드 실패:', error);
      alert('PDF 다운로드에 실패했습니다.');
    } finally {
      setIsDownloading(false);
    }
  };

  if (loading) {
    return <div>일정을 불러오는 중...</div>;
  }

  if (!itinerary) {
    return <div>일정을 찾을 수 없습니다.</div>;
  }

  return (
    <div className={styles.page}>
      <AppHeader />

      <div className={styles.wrap}>
        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>
            ✓ 최종 일정 확인
          </div>

          <h1>완성된 일정을 확인해보세요</h1>

          <p>
            여행 일정을 확인하고, 저장하거나 공유할 수 있어요.
          </p>
        </div>

        {(token || itinerary.status !== 'confirmed') && (
        <div className={styles.shell}>
          <div
            className={styles.mainCard}
            ref={pdfRef}
          >
            <div className={styles.topRow}>
              <div>
                <h2>
                  {itinerary.durationLabel} {itinerary.companionTypeDisplay} 여행
                </h2>
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
                      styles.sm
                    )}
                    onClick={handleShare}
                  >
                    📤 공유하기
                  </button>

                  <button
                    className={cx(
                      styles.btn,
                      styles.ghost,
                      styles.sm
                    )}
                    onClick={handlePdfDownload}
                    disabled={isDownloading}
                  >
                    {isDownloading
                      ? 'PDF 생성 중...'
                      : '📄 PDF 다운로드'}
                  </button>

                  {itinerary.status !== 'confirmed' && (
                    <Link
                      to={`/itinerary/${id}`}
                      className={cx(styles.btn, styles.ghost, styles.sm)}
                  >
                    ✏️ 일정 수정하기
                    </Link>
                  )}

                  <Link
                    to="/my/itineraries"
                    className={cx(styles.btn, styles.ghost, styles.sm)}
                  >
                    📅 내 일정
                  </Link>
                </div>
              )}
            </div>

            <div className={styles.metaRow}>
              <div className={styles.metaItem}>
                📅 {itinerary.durationLabel}
              </div>

              <div className={styles.metaItem}>
                👥 {itinerary.companionTypeDisplay}
              </div>

              <div className={styles.metaItem}>
                🍃 {itinerary.styleDisplay}
              </div>
            </div>

            <div className={styles.grid}>
              <div className={styles.dayArea}>
                <DayColumns days={itinerary.days} />
              </div>
              <TripSummary itinerary={itinerary} />
            </div>
          </div>

        </div>
        )}

          {!token && itinerary.status === 'confirmed' && (
            <section className={styles.packageComparison}>
              <div className={styles.packageComparisonHead}>
                <span>상품 선택</span>
                <h2>두 여행 일정을 한눈에 비교해보세요</h2>
                <p>추천 패키지와 내가 만든 자유일정 중 하나를 선택할 수 있어요.</p>
              </div>

              <div
                id="package-comparison-map"
                className={styles.comparisonMapSlot}
                data-itinerary-id={itinerary.id}
              >
                {packageComparison?.stored_package ? (
                  <ComparisonRouteMap
                    itineraryId={itinerary.id}
                    storedDays={packageComparison.stored_package.days}
                  />
                ) : (
                  <div className={styles.comparisonMapGuide}>
                    <strong>두 일정 동선 비교 지도</strong>
                    <p>추천 패키지와 자유일정의 이동 경로가 이 영역에 표시됩니다.</p>
                  </div>
                )}
              </div>

              {packageLoading && (
                <p className={styles.packageMessage}>상품 가격을 계산하고 있어요.</p>
              )}

              {!packageLoading && packageError && (
                <p className={styles.packageMessage}>{packageError}</p>
              )}

              {!packageLoading && !packageError && packageComparison && (
                <div className={styles.packageComparisonGrid}>
                  <article
                    className={cx(
                      styles.packageChoiceCard,
                      styles.recommendedChoiceCard,
                      selectedProduct === 'stored' && styles.selectedChoiceCard
                    )}
                    onClick={() => setSelectedProduct('stored')}
                    role="radio"
                    aria-checked={selectedProduct === 'stored'}
                    tabIndex={0}
                  >
                    <div className={styles.bestMatchRibbon}>
                      BEST MATCH
                    </div>
                    <div
                      className={cx(
                        styles.selectionStatus,
                        selectedProduct === 'stored' && styles.selectionStatusActive
                      )}
                    >
                      {selectedProduct === 'stored' ? '✓ 선택됨' : '○ 선택하기'}
                    </div>
                    <div className={styles.packageChoiceHead}>
                      <div>
                        <span className={cx(styles.packageBadge, styles.recommendedBadge)}>
                          우리 여행사 추천 패키지
                        </span>
                        <h3>
                          {packageComparison.stored_package?.title ??
                            '조건에 맞는 패키지가 없습니다'}
                        </h3>
                      </div>
                      {packageComparison.stored_package && (
                        <strong>
                          {formatPrice(packageComparison.stored_package.estimated_price)}
                          <small> / 1인</small>
                        </strong>
                      )}
                    </div>
                    {packageComparison.stored_package && (
                      <>
                        <p className={styles.packageMeta}>
                          {packageComparison.stored_package.region} ·{' '}
                          {packageComparison.stored_package.duration_days}일
                        </p>
                        <ComparisonDays
                          days={packageComparison.stored_package.days}
                        />
                        <div className={styles.packageAdvantages}>
                          <span>✓ 확정 일정과 가장 유사한 구성</span>
                          <span>✓ 바로 예약 가능한 패키지 상품</span>
                        </div>
                      </>
                    )}
                  </article>

                  <article
                    className={cx(
                      styles.packageChoiceCard,
                      styles.customChoiceCard,
                      selectedProduct === 'custom' && styles.selectedChoiceCard
                    )}
                    onClick={() => setSelectedProduct('custom')}
                    role="radio"
                    aria-checked={selectedProduct === 'custom'}
                    tabIndex={0}
                  >
                    <div
                      className={cx(
                        styles.selectionStatus,
                        selectedProduct === 'custom' && styles.selectionStatusActive
                      )}
                    >
                      {selectedProduct === 'custom' ? '✓ 선택됨' : '○ 선택하기'}
                    </div>
                    <div className={styles.packageChoiceHead}>
                      <div>
                        <span className={cx(styles.packageBadge, styles.customBadge)}>
                          자유일정 대안
                        </span>
                        <h3>{itinerary.title || '내가 확정한 일정 그대로'}</h3>
                      </div>
                      {packageComparison.custom_package && (
                        <strong>
                          {formatPrice(packageComparison.custom_package.price_per_person)}
                          <small> / 1인</small>
                        </strong>
                      )}
                    </div>
                    {packageComparison.custom_package && (
                      <>
                        <p className={styles.packageMeta}>
                          {itinerary.durationLabel} · 일정 맞춤 구성비 포함
                        </p>
                        <ComparisonDays days={itinerary.days} custom />
                      </>
                    )}
                  </article>
                </div>
              )}

              {!packageLoading && !packageError && packageComparison && (
                <div className={styles.bookingAction}>
                  <span>
                    {selectedProduct === 'stored'
                      ? '추천 패키지를 선택했습니다.'
                      : '자유일정을 선택했습니다.'}
                  </span>
                  <div className={styles.bookingButtons}>
                    <button
                      type="button"
                      className={cx(styles.btn, styles.ghost)}
                      onClick={handleAddToCart}
                      disabled={addingToCart || (
                        selectedProduct === 'stored'
                          ? !packageComparison.stored_package?.id
                          : !packageComparison.custom_package
                      )}
                    >
                      {addingToCart ? '담는 중...' : '선택한 상품 장바구니에 넣기'}
                    </button>
                  <button
                    type="button"
                    className={cx(styles.btn, styles.primary)}
                    onClick={handleBooking}
                    disabled={
                      selectedProduct === 'stored'
                        ? !packageComparison.stored_package?.id
                        : !packageComparison.custom_package
                    }
                  >
                    선택한 상품 예약하기 →
                  </button>
                  </div>
                </div>
              )}
            </section>
          )}
      </div>
    </div>
  );
}