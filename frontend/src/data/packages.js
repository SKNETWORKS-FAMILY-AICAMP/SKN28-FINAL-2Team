export const won = (value) =>
  `${Number(value || 0).toLocaleString('ko-KR')}원`

// 백엔드는 rating(숫자)/review_count(숫자)를 따로 내려주므로, 화면 표시용 라벨은 프론트에서 조합한다.
export const ratingLabel = (pkg) => `★ ${pkg.rating} (${pkg.reviewCount})`
