import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import styles from './booking/booking.module.css';
import cx from '../utils/cx.js';

import AppHeader from '../components/AppHeader.jsx';
import PackageList from './booking/PackageList.jsx';
import PaymentSummary from './booking/PaymentSummary.jsx';
import TripInfoCard from './booking/TripInfoCard.jsx';

import { useBookmarks } from '../context/BookmarkContext.jsx';
import { useReservations } from '../context/ReservationContext.jsx';
import { useCart } from '../context/CartContext.jsx';
import { won } from '../data/packages.js';

// ============================================================
// 날짜 유틸
// ============================================================

const toDateInputValue = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');

  return `${year}-${month}-${day}`;
};

const addDays = (dateStr, days) => {
  if (!dateStr) return '';

  const d = new Date(`${dateStr}T00:00:00`);

  if (Number.isNaN(d.getTime())) {
    return '';
  }

  d.setDate(d.getDate() + days);

  return toDateInputValue(d);
};

export default function BookingPage() {
  const { addReservation } = useReservations();
  const { state } = useLocation();

  // ============================================================
  // 예약 진입 경로
  //
  // package
  //   → 전체 패키지에서 바로 예약
  //
  // custom-itinerary
  //   → LLM으로 만든 자유일정 예약
  //
  // cart
  //   → 장바구니 예약
  // ============================================================

  const bookingSource = state?.bookingSource || 'itinerary';
  const isCartBooking = bookingSource === 'cart';
  const isCustomBooking = bookingSource === 'custom-itinerary';
  const isPackageBooking = bookingSource === 'package';

  // ============================================================
  // 선택된 상품
  // ============================================================

  const initialSelected =
    bookingSource === 'package' && Array.isArray(state?.packageIds)
      ? state.packageIds
      : bookingSource === 'custom-itinerary' && Array.isArray(state?.packages)
        ? state.packages.map((item) => item.id)
        : [1, 2];

  const [selected, setSelected] = useState(initialSelected);

  // ============================================================
  // 예약 상태
  // ============================================================

  const [submitting, setSubmitting] = useState(false);

  const [confirmed, setConfirmed] = useState(false);

  const [confirmedTotal, setConfirmedTotal] = useState(0);

  const [confirmedReservation, setConfirmedReservation] = useState(null);

  const { isBookmarked, toggle: toggleBookmark } = useBookmarks();

  const { cartPackages, refreshCart } = useCart();

  const itineraryId = state?.itineraryId;

  // ============================================================
  // 상품 선택 토글
  // ============================================================

  const toggle = (id) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  // ============================================================
  // 장바구니 예약일 경우 선택 상품 동기화
  // ============================================================

  useEffect(() => {
    if (isCartBooking) {
      setSelected(cartPackages.map((item) => item.package.id));
    }
  }, [isCartBooking, cartPackages]);

  // ============================================================
  // 예약 상품 구성
  // ============================================================

  const directPackages = Array.isArray(state?.packages) ? state.packages : [];

  const packageItems = directPackages.map((p) => ({
    cartId: `package-${p.id}`,
    package: p,
    quantity: 1,
  }));

  const bookingItems = isCartBooking ? cartPackages : packageItems;

  const chosenItems = bookingItems.filter((item) => selected.includes(item.package.id));

  const chosen = chosenItems.map((item) => item.package);

  // ============================================================
  // 여행 정보
  //
  // 전체 패키지
  //   → 날짜 수정 가능
  //   → 인원 수정 가능
  //
  // LLM 자유일정
  //   → 날짜는 기존 일정 그대로
  //   → 인원 수정 가능
  // ============================================================

  const tomorrow = useMemo(() => addDays(toDateInputValue(new Date()), 1), []);

  // ------------------------------------------------------------
  // 패키지 여행 기간
  // ------------------------------------------------------------

  const packageDurationDays = Number(chosen[0]?.durationDays ?? chosen[0]?.duration_days ?? 1) || 1;

  // ------------------------------------------------------------
  // 전체 패키지에서 선택한 시작일
  // ------------------------------------------------------------

  const [pickedStartDate, setPickedStartDate] = useState(tomorrow);

  // ------------------------------------------------------------
  // 예약 화면에서 선택하는 여행 인원
  //
  // 전체 패키지 / LLM 자유일정 모두
  // 기본값은 1명
  // ------------------------------------------------------------

  const [pickedPeopleCount, setPickedPeopleCount] = useState(1);

  // ============================================================
  // 실제 여행 시작일
  // ============================================================

  const tripStartDate = isCustomBooking ? state?.startDate : pickedStartDate;

  // ============================================================
  // 실제 여행 종료일
  // ============================================================

  const tripEndDate = isCustomBooking ? state?.endDate : tripStartDate ? addDays(tripStartDate, packageDurationDays - 1) : '';

  // ============================================================
  // 예약에 사용할 인원
  //
  // LLM 자유일정도 기존 companionCount를 사용하지 않고
  // 예약 화면에서 선택한 pickedPeopleCount 사용
  // ============================================================

  const bookingPeopleCount = isPackageBooking || isCustomBooking ? pickedPeopleCount : 1;

  // ============================================================
  // 여행 정보 카드 표시 여부
  // ============================================================

  const showTripInfo = isCustomBooking || isPackageBooking;

  // ============================================================
  // 총 결제 금액
  //
  // 전체 패키지:
  //   1인 가격 × 선택 인원
  //
  // LLM 자유일정:
  //   1인 가격 × 선택 인원
  //
  // 장바구니:
  //   상품 가격 × 수량
  // ============================================================

  const total = chosenItems.reduce((sum, item) => {
    const price = Number(item.package.price) || 0;

    if (isPackageBooking || isCustomBooking) {
      return sum + price * bookingPeopleCount;
    }

    return sum + price * item.quantity;
  }, 0);

  // ============================================================
  // 예약 확정
  // ============================================================

  const handleConfirm = async () => {
    setSubmitting(true);

    try {
      const reservation = await addReservation('신용카드 (**** **** **** 1234)', {
        packageIds: isCartBooking || isCustomBooking ? undefined : chosen.map((p) => p.id),

        cartItemIds: isCartBooking ? chosenItems.map((item) => item.cartId) : undefined,

        itineraryId,

        startDate: isPackageBooking ? tripStartDate : undefined,

        peopleCount: isPackageBooking || isCustomBooking ? bookingPeopleCount : undefined,
      });

      setConfirmedTotal(total)
      setConfirmedReservation(reservation);
      setConfirmed(true);

      if (isCartBooking) {
        await refreshCart();
      }
    } catch (error) {
      console.error('예약 생성 실패:', error);

      alert(error.message || '예약에 실패했어요. 다시 시도해주세요.');
    } finally {
      setSubmitting(false);
    }
  };

  // ============================================================
  // 예약 완료 화면에 표시할 상품명
  // ============================================================

  const confirmedItemNames = confirmedReservation?.items?.map((item) => item.name).filter(Boolean) ?? [];

  const confirmedTitle = confirmedItemNames.length > 0 ? confirmedItemNames.join(', ') : '예약한 제주 패키지';

  // ============================================================
  // 예약 완료 날짜
  // ============================================================

  const confirmedDate = confirmedReservation?.created_at ? new Date(confirmedReservation.created_at).toLocaleDateString('ko-KR') : '';

  // ============================================================
  // 예약 완료 화면에서 사용할 실제 여행 인원
  // ============================================================

  const confirmedPeopleCount = confirmedReservation?.people_count ?? confirmedReservation?.peopleCount ?? bookingPeopleCount ?? 1;

  // ============================================================
  // 화면
  // ============================================================

  return (
    <div className={styles.page}>
      <AppHeader />

      <div className={styles.wrap}>
        {!confirmed && (
          <Link to={itineraryId ? `/review/${itineraryId}` : '/packages'} className={styles.backLink}>
            ← {itineraryId ? '일정으로 돌아가기' : '패키지로 돌아가기'}
          </Link>
        )}

        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 예약 및 결제</div>

          <h1>{confirmed ? '결제가 완료됐어요!' : '예약 전 마지막으로 확인해주세요'}</h1>

          <p>
            {confirmed
              ? '예약이 정상적으로 확정되었습니다.'
              : bookingSource === 'package'
                ? '선택한 패키지와 결제 금액을 확인해주세요.'
                : bookingSource === 'custom-itinerary'
                  ? '선택한 일정과 결제 금액을 확인해주세요.'
                  : bookingSource === 'cart'
                    ? '장바구니에 담은 상품과 결제 금액을 확인해주세요.'
                    : '선택한 여행 상품과 결제 금액을 확인해주세요.'}
          </p>
        </div>

        {confirmed ? (
          <div className={styles.successCard}>
            <div className={styles.successBadge}>✓</div>

            <h2>예약이 확정됐어요 🎉</h2>

            <p>
              {confirmedTitle} 예약이 완료됐어요.
              <br />
              "예약 내역"에서 언제든 다시 확인할 수 있어요.
            </p>

            <div className={styles.successMeta}>
              <div className={styles.row}>
                <span className={styles.k}>여행 기간</span>

                <span className={styles.v}>{tripStartDate && tripEndDate ? `${tripStartDate} ~ ${tripEndDate}` : '기간 정보 없음'}</span>
              </div>

              <div className={styles.row}>
                <span className={styles.k}>여행 인원</span>

                <span className={styles.v}>{confirmedPeopleCount}명</span>
              </div>

              <div className={styles.row}>
                <span className={styles.k}>예약 일자</span>

                <span className={styles.v}>{confirmedDate || '예약 완료'}</span>
              </div>

              <div className={styles.row}>
                <span className={styles.k}>결제 금액</span>

                <span className={styles.v}>{won(confirmedTotal)}</span>
              </div>
            </div>

            <div
              style={{
                marginTop: 26,
                display: 'flex',
                gap: 10,
                justifyContent: 'center',
              }}
            >
              <Link to="/my/reservations" className={cx(styles.btn, styles.ghost)}>
                예약 내역 보기
              </Link>

              <Link to="/" className={cx(styles.btn, styles.primary)}>
                홈으로
              </Link>
            </div>
          </div>
        ) : (
          <div className={styles.shell}>
            <div>
              <PackageList
                items={bookingItems}
                selected={selected}
                onToggle={toggle}
                isBookmarked={isBookmarked}
                onToggleBookmark={toggleBookmark}
              />

              {showTripInfo && (
                <TripInfoCard
                  startDate={tripStartDate}
                  endDate={tripEndDate}
                  editableDate={isPackageBooking}
                  editablePeople={isPackageBooking || isCustomBooking}
                  onStartDateChange={setPickedStartDate}
                  peopleCount={pickedPeopleCount}
                  onPeopleCountChange={setPickedPeopleCount}
                  minStartDate={tomorrow}
                />
              )}
            </div>

            <PaymentSummary items={chosenItems} totalPrice={total} onConfirm={handleConfirm} submitting={submitting} />
          </div>
        )}
      </div>
    </div>
  );
}
