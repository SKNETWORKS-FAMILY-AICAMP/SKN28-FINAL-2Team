// 패키지 가격/평점 표시용 공통 포맷 헬퍼.
// (예전엔 이 파일에 API 연동 전 사용하던 목업 패키지 배열(PACKAGES)도 있었으나,
//  실제 백엔드 연동이 끝나 더 이상 어디서도 참조되지 않아 제거했다.)

export const won = (n) => Number(n || 0).toLocaleString('ko-KR') + '원'

// 백엔드는 rating(숫자)/review_count(숫자)를 따로 내려주므로, 화면 표시용 라벨은 프론트에서 조합한다.
export const ratingLabel = (pkg) => `★ ${pkg.rating} (${pkg.reviewCount})`
