# TourAPI Collection

## Source

- 서비스: 한국관광공사 TourAPI `KorService2`
- 기본 URL: `https://apis.data.go.kr/B551011/KorService2`
- 인증: 공공데이터포털에서 발급한 일반 인증키(Decoding)
- 환경 변수: `KOREA_TOUR_API_KEY`
- 기본 일일 호출 예산: 1,000회

API 키는 `.env`에서만 관리하고 코드·문서·Git에 기록하지 않습니다.

## Collection Scope

HubSearch 분류와 가깝게 맞추기 위해 전국 신분류 목록을 받은 뒤 주소가 제주인
레코드만 필터링합니다. 지역 코드만 사용하면 TourAPI 레코드의 지역 메타데이터가
누락되거나 서로 달라 HubSearch보다 적게 수집될 수 있습니다.

| 데이터셋 | lclsSystm1 | 현재 원본 건수 |
| --- | --- | ---: |
| 관광지 | `NA`, `HS`, `EX`, `VE` | 674 |
| 숙박 | `AC` | 220 |
| 음식점 | `FD` | 722 |
| 레저스포츠 | `LS` | 113 |
| 쇼핑 | `SH` | 395 |
| 합계 | | 2,124 |

목록 수집 후 각 `contentid`에 대해 다음 endpoint를 이어받아 호출합니다.

- `detailCommon2`: 주소, 좌표, 설명, 홈페이지, 대표 이미지 등
- `detailIntro2`: 콘텐츠 유형별 운영시간, 휴무일, 주차, 메뉴, 객실 등

## Resume Behavior

통합 CSV의 `common_fetch_status`, `intro_fetch_status`가 완료 상태인지 확인하고
미완료 건만 호출합니다. 완료 상태는 다음과 같습니다.

- `success`: 응답 수집 완료
- `no_data`: API가 해당 상세정보를 제공하지 않음
- `skipped_policy`: 전처리 정책상 소개 조회를 생략

10~25건마다 CSV를 저장하므로 429, 502, 연결 종료가 발생해도 같은 명령으로
이어받을 수 있습니다.

```powershell
python -m scripts.crawler.crawl_products --plan-only
python -m scripts.crawler.crawl_products --call-budget 950 --checkpoint-every 10
```

`--call-budget`은 계정 한도가 아니라 해당 실행에서 사용할 수 있는 남은 호출 수입니다.

## Classification Codes

```powershell
python -m scripts.crawler.fetch_lcls_codes
python -m scripts.crawler.fetch_lcls_codes --json
```

결과는 `data/raw/korea_tour_openapi_lcls_codes.csv`에 저장됩니다.
DB가 1·2·3단계 분류명을 모두 사용할 수 있도록 기본 깊이는 3입니다. JSON 사본은
`--json`을 지정한 경우에만 생성합니다.
