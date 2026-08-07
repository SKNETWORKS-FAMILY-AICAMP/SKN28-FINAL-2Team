# 제주 가상 여행 패키지 데이터셋

이 디렉터리는 평가를 거쳐 최종 선정된 제주 여행 패키지 데이터와 평가 결과를 보관합니다.

## 파일

- `final_packages.30.json`: 실제 서비스 및 DB 적재에 사용하는 최종 30개 패키지
- `final_package_evaluation.30.json`: 100개 후보의 평가 점수와 최종 30개 선정 근거

`final_packages.30.json`의 각 패키지는 다음 정보를 포함합니다.

- 패키지 ID, 제목, 요약, 권역, 여행 일수, 예상 가격
- 동행 유형·테마·여행 속도 매칭 프로필
- 일자별 관광지 3~4곳
- 일자별 식당 1곳
- 숙박 패키지의 호텔 1곳
- TourAPI `content_id` 기반 장소 연결

## 검증

프로젝트 루트에서 다음 명령으로 JSON 구조를 검증합니다.

```bash
python scripts/load_final_packages.py --validate-only
```

## MySQL 적재

먼저 기존 TourAPI 장소 데이터가 `places` 테이블에 적재되어 있어야 합니다. `.env`에 MySQL 접속 정보를 설정한 뒤 실행합니다.

```bash
python scripts/load_final_packages.py --env-file .env
```

적재 스키마는 `src/storage/sql/package_schema.sql`에 있으며 다음 테이블을 생성합니다.

- `travel_packages`: 패키지 기본 정보와 매칭 프로필
- `package_items`: 관광지·식당·호텔의 일정 순서와 TourAPI 장소 연결
