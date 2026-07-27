# 탐나플랜 (React + Vite, 5-page 흐름)

원본 HTML/디자인 목업 5개를 기반으로 React + Vite + React Router 구조로 분리해
하나의 흐름으로 연결한 프로젝트입니다.

**흐름**:
랜딩(`/`) → "무료로 일정 만들기" → AI 대화(`/chat`) → "일정 확인하기" →
일정 확인·수정(`/itinerary`) → "이 일정으로 확정하기" → 최종 검토(`/review`) →
"이 일정으로 확정하기" → 예약·결제(`/booking`) → 예약 완료

## 구조

```
src/
  components/            랜딩 페이지(1page) 섹션 컴포넌트

  pages/
    LandingPage.jsx        "/"           1page — 랜딩
    ChatPage.jsx            "/chat"       2page — AI 대화로 조건 수집
      chat/  (chat.module.css, AppHeader, ChatColumn, SummaryColumn)

    ItineraryPage.jsx       "/itinerary"  3page — 일정 확인 및 수정
      itinerary/  (itinerary.module.css, AppHeader, ChatPanel, ItineraryEditor, MapPanel)

    ReviewPage.jsx          "/review"     4page — 최종 일정 확인 (확정 전 검토)
      review/
        review.module.css    4page 전용 스타일 (CSS Modules)
        AppHeader.jsx         상단 앱 헤더
        ItineraryOverview.jsx 좌측 Day 내비게이션 + 3일치 일정을 한 화면에 보여주는
                               컬럼들 (Day 버튼 클릭 시 해당 컬럼으로 스크롤)
        TripSummary.jsx       우측 "여행 요약" 패널 — 미니 지도 + 카테고리별 예상 비용 +
                               총 합계

    BookingPage.jsx          "/booking"    5page — 예약 및 저장 (최종 확정)
      booking/
        booking.module.css   5page 전용 스타일 (CSS Modules)
        AppHeader.jsx         상단 앱 헤더 (이미 로그인된 상태를 가정해 로그인 버튼 없음)
        PackageList.jsx       체크박스로 숙소/렌터카/액티비티 패키지를 선택하는 리스트
                               (실제로 클릭해서 선택/해제 가능)
        PaymentSummary.jsx    선택한 패키지에 따라 실시간으로 재계산되는 결제 정보 +
                               "예약 및 결제하기" 버튼
      결제 버튼을 누르면 짧은 로딩 후 예약 완료 화면(성공 카드)으로 전환됩니다.

  hooks/
    useReveal.js           스크롤 reveal 애니메이션 (IntersectionObserver, 랜딩 페이지 전용)
  utils/
    cx.js                  CSS Module 클래스 여러 개를 합치는 작은 헬퍼
  App.jsx                  <Routes>로 5개 페이지를 라우팅
  main.jsx                 React 엔트리 포인트 (BrowserRouter로 감쌈)
  index.css                랜딩 페이지 전역 스타일 (원본 <style> 그대로 이전)
index.html                 Vite 엔트리 HTML (Google Fonts 포함)
```

## 원본 대비 변경점

- 4page·5page는 제공된 디자인 목업(이미지)에 실제 텍스트/레이아웃만 있고 스타일이
  없었기 때문에, 1~3page에서 이미 쓰인 디자인 시스템(Gaegu 디스플레이 폰트, 2.5px
  잉크색 테두리 + 오프셋 박스섀도, 초록 포인트 컬러, 알약형 버튼 등)을 그대로 적용해
  새로 만들었습니다.
- 모든 페이지의 CTA(`무료로 일정 만들기`, `일정 확인하기`, `이 일정으로 확정하기`,
  `예약 및 결제하기` 등)가 실제로 다음 페이지로 이동하도록 `react-router-dom`의
  `<Link>`/`useNavigate`로 연결했습니다.
- 각 page 폴더(`chat/`, `itinerary/`, `review/`, `booking/`)는 서로 겹치는 클래스명
  (`.btn`, `.logo`, `.card` 등)이 있어서 전부 **CSS Modules**로 스코프 처리해 충돌을
  방지했습니다.
- 4page(`/review`)는 이미지 목업에는 없던 상호작용을 추가했습니다: 좌측 Day 버튼을
  누르면 해당 날짜의 컬럼으로 부드럽게 스크롤됩니다.
- 5page(`/booking`)는 목업이 정적 이미지였던 것과 달리, 패키지 체크박스를 실제로
  클릭해서 선택/해제할 수 있고, 그에 따라 오른쪽 결제 금액이 즉시 재계산됩니다.
  "예약 및 결제하기"를 누르면 짧은 로딩 후 예약 완료 화면으로 전환됩니다(다음 페이지가
  없으므로, 완료 상태를 같은 페이지 안에서 보여주는 방식으로 흐름을 마무리했습니다).
- 2page의 "typing" 완료 후 등장하는 안내 메시지, 3page의 "이 일정으로 확정하기" 버튼도
  각각 다음 단계로 실제 이동하도록 연결되어 있습니다 (이전 대화에서 이미 반영됨).
- `.reveal` 요소에 대한 `IntersectionObserver` 로직은 `useReveal` 커스텀 훅으로 분리해
  `LandingPage.jsx`에서 한 번만 실행합니다.
- 모든 콘텐츠 데이터는 각 컴포넌트 상단의 배열로 분리해 유지보수하기 쉽게 만들었습니다.

## 실행 방법

```bash
npm install
npm run dev       # 개발 서버 실행 (http://localhost:5173)
npm run build     # 프로덕션 빌드 (dist/ 생성)
npm run preview   # 빌드 결과 미리보기
```

## 라우트

| 경로          | 페이지                                        |
| ------------- | ---------------------------------------------- |
| `/`           | 랜딩 페이지 (1page)                             |
| `/chat`       | AI와 대화하며 조건을 입력하는 화면 (2page)       |
| `/itinerary`  | AI 채팅 + 일정 편집 + 지도 화면 (3page)          |
| `/review`     | 최종 일정 확인 — 확정 전 검토 (4page)            |
| `/booking`    | 패키지 선택 + 예약/결제 (5page)                  |
