// AI 대화 페이지의 4단계 가이드 질문 정의.
// type: 'toggle' → 옵션 버튼 중 하나를 선택해서 답변
// type: 'text'   → 입력창에 직접 타이핑해서 답변 (단답형)
export const STEPS = [
  {
    key: 'companion',
    question: '누구랑 가시나요?',
    type: 'toggle',
    options: ['혼자', '가족', '친구', '연인'],
    icon: '👥',
    label: '동행자',
  },
  {
    key: 'travelDates',
    question: '여행 날짜를 선택해주세요.',
    type: 'dateRange',
    icon: '📅',
    label: '여행 기간',
  },
  {
    key: 'style',
    question: '여행 스타일은 어떤 걸 선호하시나요?',
    type: 'toggle',
    options: ['힐링', '액티비티', '맛집', '트레킹'],
    icon: '🍃',
    label: '여행 스타일',
  },
]

export const INITIAL_ANSWERS = STEPS.reduce((acc, s) => ({ ...acc, [s.key]: null }), {})
