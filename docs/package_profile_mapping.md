# 패키지 동반자·태그 컬럼 매핑

## 최종 DB 구조

패키지 추천 조건은 `travel_packages` 테이블의 문자열 컬럼 두 개에 저장한다.

| 컬럼 | 형식 | 예시 |
|---|---|---|
| `companion` | 쉼표로 구분한 동반자 태그 | `friend,couple` |
| `tags` | 쉼표로 구분한 패키지 여행 테마 | `nature,culture,experience` |

별도의 동반자/태그 테이블이나 유형별 Boolean 컬럼은 만들지 않는다. 기존
`match_profile` JSON도 패키지 추천 조회에는 사용하지 않는다. 한 패키지가 여러
조건에 해당하면 같은 컬럼 안에 태그를 쉼표로 이어서 저장한다.

## 동반자 태그

- `solo`: 혼자
- `friend`: 친구, 형제·자매, 친목 단체·모임
- `couple`: 연인, 배우자
- `family`: 자녀, 부모, 조부모 및 가족 여행

기존 패키지 조건은 다음처럼 변환한다.

| 기존 값 | `companion`에 저장할 값 |
|---|---|
| `solo` | `solo` |
| `non_family_two` | `friend,couple` |
| `non_family_group` | `friend` |
| `family_two` | `couple,family` |
| `family_group`, `with_children`, `with_parents`, `three_generations` | `family` |

## 패키지 여행 테마

패키지에 포함된 TourAPI 장소의 설명 태그를 모아 `travel_packages.tags`에 부여한다.

| TourAPI 값 | `tags`에 저장할 값 |
|---|---|
| `tags`에 `자연관광` 포함 | `nature` |
| `tags`에 `문화시설` 포함 | `culture` |
| `tags`에 `축제` 포함 | `festival` |
| `tags`에 `체험` 포함 | `experience` |

## 패키지 내 개별 장소 태그

장소의 실제 유형은 패키지 전체 테마와 섞지 않고 `package_items.tags`에 장소별로
저장한다.

| TourAPI `place_subtype` | `package_items.tags`에 저장할 값 |
|---|---|
| `restaurant` | `food` |
| `cafe_tea` | `cafe` |
| `water_leisure`, `land_leisure` | `activity` |
| `market`, `general_retail`, `local_specialty` | `shopping` |

`tags`는 장소 수를 나타내는 숫자가 아니라, 해당 유형을 포함하는지를 나타내는
태그 목록이다.

## 팀원 DB 적용 방법

최신 브랜치를 받은 뒤 `tour_recommender` DB에 아래 SQL 파일 하나를 실행한다.

```powershell
mysql -u root -p tour_recommender < scripts/sql/migrate_package_companion_tags_50.sql
```

MySQL Workbench에서 해당 SQL 파일을 열어 전체 실행해도 된다. 이 SQL은 다음 작업을
한 번에 수행하며 다시 실행해도 안전하게 구성한다.

1. `companion`, `tags` 컬럼이 없으면 추가
2. 패키지 50개의 동반자와 여행 테마 입력
3. `package_items.tags`를 추가하고 각 장소의 유형 태그 입력
4. 기존 `match_profile` 및 잘못 생성된 유형별 Boolean 컬럼이 있으면 제거
5. 적용 결과 조회

AIHub, TourAPI, `package_items` 등 다른 데이터는 변경하지 않는다.

## 추천 점수 반영

- 관광지 `content_id` 일치: 50점
- 동반자 태그 일치: 20점
- 장소 유형 태그 일치: 20점
- 지역 및 동선 유사도: 10점

DB에는 문자열로 저장하지만 API 응답에서는 프론트가 사용하기 편하도록 배열로
변환한다.

```json
{
  "companion_types": ["friend", "couple"],
  "tags": ["nature", "culture", "experience"]
}
```
