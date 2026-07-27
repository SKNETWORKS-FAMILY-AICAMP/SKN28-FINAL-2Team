// 백엔드 GET /api/travel/packages/ 응답 형태와 필드명을 맞춘 목업 데이터.
// (아직 실제로 fetch하지 않음 — 나중에 이 배열을 API 응답으로 교체하면 됨)
// 값 자체도 backend/apps/travel/management/commands/seed_travel_data.py 의 시드값과 동일하게 맞춤.

export const PACKAGES = [
  {
    id: 1,
    name: '오션뷰 힐링 숙소',
    category: 'stay',
    categoryLabel: '숙소',
    style: 'healing',
    description: '협재 오션스테이 2박 패키지',
    thumbnail: '🏨',
    price: 159000,
    durationDays: 2,
    accommodationIncluded: true,
    includedItems: ['오션뷰 객실', '조식 2인'],
    rating: 4.6,
    reviewCount: 321,
  },
  {
    id: 2,
    name: '렌터카 3일',
    category: 'car',
    categoryLabel: '렌터카',
    style: 'family',
    description: '아반떼 CN7 (자차 포함) 3일 대여',
    thumbnail: '🚗',
    price: 89700,
    durationDays: 3,
    accommodationIncluded: false,
    includedItems: ['자차보험', '내비게이션', '블랙박스'],
    rating: 4.7,
    reviewCount: 532,
  },
  {
    id: 3,
    name: '제주 승마 체험 2인',
    category: 'activity',
    categoryLabel: '액티비티',
    style: 'activity',
    description: '숲속 승마 트래킹 체험 (2인 기준)',
    thumbnail: '🐴',
    price: 70000,
    durationDays: 1,
    accommodationIncluded: false,
    includedItems: ['승마 장비 대여', '안전 교육', '기념사진'],
    rating: 4.8,
    reviewCount: 218,
  },
]

export const won = (n) => n.toLocaleString('ko-KR') + '원'

// 백엔드는 rating(숫자)/review_count(숫자)를 따로 내려주므로, 화면 표시용 라벨은 프론트에서 조합한다.
export const ratingLabel = (pkg) => `★ ${pkg.rating} (${pkg.reviewCount})`
