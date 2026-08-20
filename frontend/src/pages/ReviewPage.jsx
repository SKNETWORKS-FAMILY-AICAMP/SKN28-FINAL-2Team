import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import styles from './review/review.module.css';
import cx from '../utils/cx.js';
 import AppHeader from '../components/AppHeader.jsx'
import { DayColumns } from './review/ItineraryOverview.jsx';
import TripSummary from './review/TripSummary.jsx';
import ComparisonRouteMap from './review/ComparisonRouteMap.jsx';
import { useCart } from '../context/CartContext.jsx';
import { useItineraries } from '../context/ItineraryContext.jsx';
import { getPackageDetail, getPackages } from '../api/packageApi.js';

import { useEffect, useRef, useState } from 'react';

import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

import {
  createShareLink,
  getItinerary,
  getPackageRecommendations,
  getSharedItinerary,
  prepareItineraryForEdit,
} from '../api/itinerary';

const getCustomPackageThumbnail = (itinerary) => {
  const days = itinerary?.days || [];

  for (const day of days) {
    const firstItem = (day.items || []).find(
      (item) =>
        item.item_type !== 'restaurant' &&
        item.thumbnail
    );

    if (firstItem) {
      return firstItem.thumbnail;
    }
  }

  return '';
};

const formatPrice = (value) =>
  `${Number(value || 0).toLocaleString('ko-KR')}원`;

const formatCustomPrice = (customPackage) =>
  customPackage?.pricing_basis === 'free_day_trip'
    ? '무료'
    : formatPrice(customPackage?.price_per_person);

const isFreeCustomPackage = (customPackage) => Boolean(
  customPackage && (
    customPackage.pricing_basis === 'free_day_trip' ||
    Number(customPackage.price_per_person) === 0
  )
);

const hasStoredPackageIdentifier = (storedPackage) => Boolean(
  storedPackage?.id ??
  storedPackage?.package_db_id ??
  storedPackage?.package_id
);

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
  const [searchParams] = useSearchParams();
  const isItineraryOnlyView = searchParams.get('view') === 'itinerary';
  const { addToCart, addCustomToCart, openCart } = useCart();
  const { refresh: refreshItineraries } = useItineraries();

  const [itinerary, setItinerary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showToast, setShowToast] = useState(false);
  const [packageComparison, setPackageComparison] = useState(null);
  const [packageLoading, setPackageLoading] = useState(false);
  const [packageError, setPackageError] = useState('');
  const [selectedProduct, setSelectedProduct] = useState('custom');
  const [addingToCart, setAddingToCart] = useState(false);
  const [isPreparingEdit, setIsPreparingEdit] = useState(false);

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

        if (
          !token &&
          data.status === 'confirmed' &&
          (!isItineraryOnlyView || data.bookedProductType === 'stored_package')
        ) {
          setPackageLoading(true);
          setPackageError('');

          try {
            // 추천 패키지를 이미 예약한 경우
            if (
              data.bookedProductType === 'stored_package' &&
              data.bookedPackageDbId
            ) {
              const packageDetail = await getPackageDetail(
                data.bookedPackageDbId
              );

              setPackageComparison({
                stored_package: packageDetail,
                custom_package: null,
              });

              setSelectedProduct('stored');
            }

            // 자유일정을 이미 예약한 경우
            else if (
              data.bookedProductType === 'custom_itinerary'
            ) {
              setPackageComparison(null);
              setSelectedProduct('custom');
            }

            // 아직 예약 전
            else {
              const comparison = await getPackageRecommendations(id, 1);
              setPackageComparison(comparison);
              if (!comparison?.stored_package && comparison?.custom_package) {
                setSelectedProduct('custom');
              }
            }
          } catch (error) {
            console.error(error);

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
  }, [id, token, isItineraryOnlyView]);

  const handleBooking = async () => {
    const storedPackage = packageComparison?.stored_package;
    const customPackage = packageComparison?.custom_package;

    if (selectedProduct === 'stored') {
      if (!hasStoredPackageIdentifier(storedPackage)) return;

      let storedPackageDbId = storedPackage.id ?? storedPackage.package_db_id;

      if (!storedPackageDbId && storedPackage.package_id) {
        try {
          const packageResponse = await getPackages();
          const packages = Array.isArray(packageResponse)
            ? packageResponse
            : packageResponse?.results || [];
          storedPackageDbId = packages.find(
            (item) => item.package_id === storedPackage.package_id
          )?.id;
        } catch (error) {
          console.error('추천 패키지 DB 번호 조회 실패:', error);
        }
      }

      if (!storedPackageDbId) {
        alert('선택한 패키지 정보를 찾지 못했습니다. 잠시 후 다시 시도해주세요.');
        return;
      }

      let packageDetail = null;
      try {
        packageDetail = await getPackageDetail(storedPackageDbId);
      } catch (error) {
        console.error('패키지 상세 이미지 조회 실패:', error);
      }

      navigate('/booking', {
        state: {
          bookingSource: 'package',
          itineraryId: itinerary.id,
          startDate: itinerary.startDate,
          endDate: itinerary.endDate,
          peopleCount: itinerary.companionCount,
          packageIds: [storedPackageDbId],
          packages: [
            {
              id: storedPackageDbId,
              packageId: storedPackage.package_id,
              name: storedPackage.title,
              description: storedPackage.summary || storedPackage.reason || '',
              price: storedPackage.estimated_price,
              thumbnailUrl: packageDetail?.thumbnail_url || '',
              thumbnail: '✈️',
              durationDays:
                storedPackage.duration_days ?? packageDetail?.duration_days,
              region: storedPackage.region ?? packageDetail?.region,
              accommodationIncluded: Boolean(
                storedPackage.hotel ?? packageDetail?.accommodation_included,
              ),
              accommodationName:
                storedPackage.hotel?.title ?? packageDetail?.accommodation_name ?? '',
            },
          ],
        },
      });
      return;
    }

    if (!customPackage) return;
    if (isFreeCustomPackage(customPackage)) {
      await refreshItineraries();
      navigate(`/review/${itinerary.id}?view=itinerary`);
      return;
    }

    navigate('/booking', {
      state: {
        bookingSource: 'custom-itinerary',
        itineraryId: itinerary.id,
        startDate: itinerary.startDate,
        endDate: itinerary.endDate,
        peopleCount: itinerary.companionCount,
        packages: [
          {
            id: `custom-${itinerary.id}`,
            name: itinerary.title || '내가 만든 일정',
            description: '대화로 완성한 일정 그대로 여행하는 자유일정이에요.',
            price: customPackage.price_per_person,
            thumbnailUrl: getCustomPackageThumbnail(itinerary),
            thumbnail: '🧭',
            isCustom: true,
            durationLabel: itinerary.duration_label,
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
        if (!hasStoredPackageIdentifier(storedPackage)) return;

        let storedPackageDbId = storedPackage.id ?? storedPackage.package_db_id;
        if (!storedPackageDbId && storedPackage.package_id) {
          const packageResponse = await getPackages();
          const packages = Array.isArray(packageResponse)
            ? packageResponse
            : packageResponse?.results || [];
          storedPackageDbId = packages.find(
            (item) => item.package_id === storedPackage.package_id
          )?.id;
        }
        if (!storedPackageDbId) {
          throw new Error('선택한 패키지 정보를 찾지 못했습니다.');
        }
        await addToCart(storedPackageDbId, { itineraryId: itinerary.id });
      } else {
        if (!customPackage) return;
        if (isFreeCustomPackage(customPackage)) {
          throw new Error('당일치기 자유일정은 무료로 제공되어 장바구니에 담을 수 없습니다.');
        }
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

  const handleEditItinerary = async () => {
    if (isPreparingEdit) return;

    try {
      setIsPreparingEdit(true);
      const result = await prepareItineraryForEdit(itinerary.id);

      refreshItineraries().catch((error) => {
        console.error('일정 목록 새로고침 실패:', error);
      });

      if (result.copied) {
        alert('예약된 원본은 보존하고 수정용 일정 복사본을 만들었습니다.');
      }

      navigate(`/itinerary/${result.itinerary.id}`);
    } catch (error) {
      console.error('일정 편집 준비 실패:', error);
      alert(
        error.response?.data?.detail ??
          '일정을 수정할 수 있는 상태로 준비하지 못했습니다.'
      );
    } finally {
      setIsPreparingEdit(false);
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

  const bookedProductType = itinerary.bookedProductType;

  const isBookedStored =
    bookedProductType === 'stored_package';

  const isBookedCustom =
    bookedProductType === 'custom_itinerary';

  const isBooked =
    isBookedStored || isBookedCustom;

  return (
    <div className={styles.page}>
      <AppHeader />

      <div className={styles.wrap}>
        {!isBooked && (
          <div className={styles.pageHead}>
          <div className={styles.sectionTag}>
            {isBooked
              ? '✓ 예약 일정 확인'
              : isItineraryOnlyView
                ? '✓ 일정 확인'
                : '✓ 최종 일정 확인'}
          </div>

          <h1>
            {isBooked
              ? '예약한 여행을 확인해보세요'
              : isItineraryOnlyView
                ? '여행 일정을 확인해보세요'
                : '나에게 맞는 여행을 선택해보세요'}
          </h1>

          <p>
            {isBooked
              ? '예약한 일정과 이동 경로를 한눈에 확인할 수 있어요.'
              : isItineraryOnlyView
                ? '완성한 일정과 이동 경로를 한눈에 확인할 수 있어요.'
                : '방금 완성한 일정을 그대로 이용하거나, 일정과 잘 맞는 추천 패키지를 선택할 수 있어요.'}
          </p>
          </div>
        )}

        {!token && !isItineraryOnlyView && !isBooked && (
          <div className={styles.reviewActions}>
            <button
              type="button"
              className={cx(styles.btn, styles.ghost, styles.sm)}
              onClick={handleEditItinerary}
              disabled={isPreparingEdit}
            >
              {isPreparingEdit
                ? '수정 준비 중...'
                : isBooked
                  ? '✏️ 복사해서 일정 수정'
                  : '✏️ 일정 수정하기'}
            </button>
          </div>
        )}


        <div>
          {(token || itinerary.status !== 'confirmed') && (
        <div className={styles.shell}>
          <div className={styles.mainCard} ref={pdfRef}>
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


                  {isItineraryOnlyView && (
                    <>
                      {showToast && (
                        <div className={styles.toast}>
                          링크 복사!
                        </div>
                      )}

                      <button
                        type="button"
                        className={cx(styles.btn, styles.ghost, styles.sm)}
                        onClick={handleShare}
                      >
                        📤 공유하기
                      </button>

                      <button
                        type="button"
                        className={cx(styles.btn, styles.ghost, styles.sm)}
                        onClick={handlePdfDownload}
                        disabled={isDownloading}
                      >
                        {isDownloading ? 'PDF 생성 중...' : '📄 PDF 저장'}
                      </button>
                    </>
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

            {itinerary.hotel && (
              <div className={styles.itineraryHotelInfo}>
                <span className={styles.accommodationIcon} aria-hidden="true">🛏</span>
                <span className={styles.accommodationCopy}>
                  <small>자유일정 포함 숙소 · {itinerary.hotel.nights}박</small>
                  <strong>{itinerary.hotel.title}</strong>
                  {itinerary.hotel.address && <em>{itinerary.hotel.address}</em>}
                </span>
                <span className={styles.accommodationIncluded}>숙박 포함</span>
              </div>
            )}

            <div className={styles.grid}>
              <div className={styles.dayArea}>
                <DayColumns days={itinerary.days} />
              </div>
              <TripSummary itinerary={itinerary} />
            </div>
          </div>

        </div>
        )}

          {!token && !isItineraryOnlyView && itinerary.status === 'confirmed' && !isBooked && (
            <section className={styles.packageComparison}>
              <div
                id="package-comparison-map"
                className={styles.comparisonMapSlot}
                data-itinerary-id={itinerary.id}
              >
                {packageComparison?.stored_package || packageComparison?.custom_package ? (
                  <ComparisonRouteMap
                    itineraryId={itinerary.id}
                    storedPackageId={packageComparison.stored_package?.id}
                    storedDays={packageComparison.stored_package?.days ?? []}
                    storedHotel={
                      packageComparison.stored_package?.hotel ??
                      packageComparison.stored_package?.accommodation ??
                      null
                    }
                    customHotel={itinerary.hotel ?? null}
                    selectedProduct={selectedProduct}
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
                    onClick={() => {
                      if (packageComparison.stored_package) setSelectedProduct('stored');
                    }}
                    role="radio"
                    aria-checked={selectedProduct === 'stored'}
                    tabIndex={0}
                  >

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
                        <div className={styles.packageBadgeRow}>
                          <span className={cx(styles.packageBadge, styles.recommendedBadge)}>
                            탐나 플랜 추천 패키지
                          </span>
                        </div>
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

                    {packageComparison.stored_package?.reason && (
                      <div className={styles.recommendReason}>
                        <strong>✨이 패키지를 추천해요</strong>
                        <p>{packageComparison.stored_package.reason}</p>
                      </div>
                    )}

                    {packageComparison.stored_package && (
                      <>
                        {Boolean(packageComparison.stored_package.hotel) && (
                          <div className={styles.accommodationInfo}>
                            <span className={styles.accommodationIcon} aria-hidden="true">🛏</span>
                            <span className={styles.accommodationCopy}>
                              <small>패키지 포함 숙소</small>
                              <strong>
                                {packageComparison.stored_package.hotel.title || '숙소 포함'}
                              </strong>
                            </span>
                            <span className={styles.accommodationIncluded}>숙박 포함</span>
                          </div>
                        )}
                        <ComparisonDays
                          days={packageComparison.stored_package.days}
                        />
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
                        <div className={styles.packageBadgeRow}>
                          <span
                            className={cx(
                              styles.packageBadge,
                              styles.customBadge
                            )}
                          >
                            내가 만든 일정
                          </span>
                        </div>

                        <h3>
                          {itinerary.title || '내가 확정한 일정 그대로'}
                        </h3>
                      </div>
                      {packageComparison.custom_package && (
                        <strong>
                          {formatCustomPrice(packageComparison.custom_package)}
                          {Number(packageComparison.custom_package.price_per_person) > 0 && (
                            <small> / 1인</small>
                          )}
                        </strong>
                      )}
                    </div>
                    {packageComparison.custom_package && (
                      <>
                        <div className={styles.recommendReason}>
                          <strong>✏️ 내 일정 그대로 여행하기</strong>
                          <p>
                            마음에 든 지금 일정 그대로, 나만의 여행을 즐겨보세요.
                          </p>
                        </div>
                        {itinerary.hotel && (
                          <div className={styles.accommodationInfo}>
                            <span className={styles.accommodationIcon} aria-hidden="true">🛏</span>
                            <span className={styles.accommodationCopy}>
                              <small>포함 숙소 · {itinerary.hotel.nights}박</small>
                              <strong>{itinerary.hotel.title}</strong>
                            </span>
                            <span className={styles.accommodationIncluded}>숙박 포함</span>
                          </div>
                        )}
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
                      ? '추천 패키지를 선택했어요.'
                      : isFreeCustomPackage(packageComparison.custom_package)
                        ? '무료 당일치기 일정은 내 일정에서 바로 확인할 수 있어요.'
                        : '내가 만든 일정을 선택했어요.'}
                  </span>
                  <div className={styles.bookingButtons}>
                    <button
                      type="button"
                      className={cx(styles.btn, styles.ghost)}
                      onClick={handleAddToCart}
                      disabled={addingToCart || (
                        selectedProduct === 'stored'
                          ? !hasStoredPackageIdentifier(packageComparison.stored_package)
                          : !packageComparison.custom_package ||
                            isFreeCustomPackage(packageComparison.custom_package)
                      )}
                    >
                      {isFreeCustomPackage(packageComparison.custom_package) && selectedProduct === 'custom'
                        ? '무료 일정은 장바구니 불필요'
                        : addingToCart
                          ? '담는 중...'
                          : '선택한 상품 장바구니에 넣기'}
                    </button>
                  <button
                    type="button"
                    className={cx(styles.btn, styles.primary)}
                    onClick={handleBooking}
                    disabled={
                      selectedProduct === 'stored'
                        ? !hasStoredPackageIdentifier(packageComparison.stored_package)
                        : !packageComparison.custom_package
                    }
                  >
                    {isFreeCustomPackage(packageComparison.custom_package) && selectedProduct === 'custom'
                      ? '일정 확인하기 →'
                      : '선택한 상품 예약하기 →'}
                  </button>
                  </div>
                </div>
              )}
            </section>
          )}
  
      {!token &&
        itinerary.status === 'confirmed' &&
        isBookedStored &&
        packageComparison?.stored_package && (
          <section className={cx(styles.packageComparison, styles.bookedComparison)}>
            <div className={styles.packageComparisonHead}>
              <span>예약한 여행</span>

              <h2>
                {packageComparison.stored_package.title ??
                  packageComparison.stored_package.name}
              </h2>

              <p>예약한 추천 패키지의 일정입니다.</p>
            </div>

            <div className={styles.reviewActions}>
              {showToast && (
                <div className={styles.toast}>
                  링크 복사!
                </div>
              )}

              <button
                type="button"
                className={cx(styles.btn, styles.ghost, styles.sm)}
                onClick={handleShare}
              >
                📤 공유하기
              </button>

              <button
                type="button"
                className={cx(styles.btn, styles.ghost, styles.sm)}
                onClick={handlePdfDownload}
                disabled={isDownloading}
              >
                {isDownloading ? 'PDF 생성 중...' : '📄 PDF 저장'}
              </button>
            </div>

            <div className={styles.comparisonMapSlot}>
              <ComparisonRouteMap
                itineraryId={itinerary.id}
                storedPackageId={packageComparison.stored_package.id}
                storedDays={
                  packageComparison.stored_package.days ??
                  packageComparison.stored_package.course ??
                  []
                }
                storedHotel={
                  itinerary.hotel ??
                  packageComparison.stored_package.hotel ??
                  packageComparison.stored_package.accommodation ??
                  null
                }
                mode="stored"
              />
            </div>

            <div
              ref={pdfRef}
              className={cx(styles.packageComparisonGrid, styles.bookedComparisonGrid)}
            >
              <article
                className={cx(
                  styles.packageChoiceCard,
                  styles.recommendedChoiceCard,
                  styles.bookedChoiceCard
                )}
              >
                <div className={styles.packageChoiceHead}>
                  <div>
                    <span
                      className={cx(
                        styles.packageBadge,
                        styles.recommendedBadge
                      )}
                    >
                      예약한 추천 패키지
                    </span>

                    <h3>
                      {packageComparison.stored_package.title ??
                        packageComparison.stored_package.name}
                    </h3>
                  </div>

                  <strong>
                    {formatPrice(
                      packageComparison.stored_package.estimated_price ??
                        packageComparison.stored_package.price
                    )}
                    <small> / 1인</small>
                  </strong>
                </div>

                {itinerary.hotel && (
                  <div className={styles.bookedAccommodationInfo}>
                    <span className={styles.accommodationIcon} aria-hidden="true">🛏</span>
                    <span className={styles.accommodationCopy}>
                      <small>패키지 포함 숙소 · {itinerary.hotel.nights}박</small>
                      <strong>{itinerary.hotel.title}</strong>
                      {itinerary.hotel.address && <em>{itinerary.hotel.address}</em>}
                    </span>
                    <span className={styles.accommodationIncluded}>숙박 포함</span>
                  </div>
                )}

                <ComparisonDays
                  days={
                    packageComparison.stored_package.days ??
                    packageComparison.stored_package.course ??
                    []
                  }
                />
              </article>
            </div>
          </section>
      )}
            {!token &&
              itinerary.status === 'confirmed' &&
              (isBookedCustom || (isItineraryOnlyView && !isBookedStored)) && (
                <section className={cx(styles.packageComparison, styles.bookedComparison)}>

                {!token && (
                  <div className={styles.reviewActions}>
                    {showToast && (
                      <div className={styles.toast}>
                        링크 복사!
                      </div>
                    )}

                    <button
                      type="button"
                      className={cx(styles.btn, styles.ghost, styles.sm)}
                      onClick={handleShare}
                    >
                      📤 공유하기
                    </button>

                    <button
                      type="button"
                      className={cx(styles.btn, styles.ghost, styles.sm)}
                      onClick={handlePdfDownload}
                      disabled={isDownloading}
                    >
                      {isDownloading ? 'PDF 생성 중...' : '📄 PDF 저장'}
                    </button>
                  </div>
                )}
                  <div className={styles.comparisonMapSlot}>
                    <ComparisonRouteMap
                      itineraryId={itinerary.id}
                      storedDays={[]}
                      customHotel={itinerary.hotel ?? null}
                      mode="custom"
                    />
                  </div>

                  <div
                    ref={pdfRef}
                    className={cx(styles.packageComparisonGrid, styles.bookedComparisonGrid)}
                  >
                    <article
                      className={cx(
                        styles.packageChoiceCard,
                        styles.customChoiceCard,
                        styles.bookedChoiceCard
                      )}
                    >
                      <div className={styles.packageChoiceHead}>
                        <div>
                          <div className={styles.packageBadgeRow}>
                            <span
                              className={cx(
                                styles.packageBadge,
                                styles.customBadge
                              )}
                            >
                              {isBookedCustom
                                ? '자유일정 패키지'
                                : '완성한 자유일정'}
                            </span>

                            {!isBookedCustom && itinerary.days?.length === 1 && (
                              <span className={styles.freeBadge}>
                                무료
                              </span>
                            )}
                          </div>

                          <h3>
                            {itinerary.durationLabel} {itinerary.companionTypeDisplay} 여행
                          </h3>
                        </div>

                        {isBookedCustom && (
                          <strong>
                            {formatPrice(itinerary.bookedPrice)}
                            <small> / 1인</small>
                          </strong>
                        )}
                      </div>

                      {itinerary.hotel && (
                        <div className={styles.bookedAccommodationInfo}>
                          <span className={styles.accommodationIcon} aria-hidden="true">🛏</span>
                          <span className={styles.accommodationCopy}>
                            <small>자유일정 숙소 · {itinerary.hotel.nights}박</small>
                            <strong>{itinerary.hotel.title}</strong>
                            {itinerary.hotel.address && <em>{itinerary.hotel.address}</em>}
                          </span>
                          <span className={styles.accommodationIncluded}>숙박 포함</span>
                        </div>
                      )}

                      <ComparisonDays
                        days={itinerary.days}
                        custom
                      />
                    </article>
                  </div>
                </section>
            )}

          </div>
        </div>  
      </div>  
  );
}
