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
    key: 'ageGroup',
    question: '여행하시는 분의 나이대를 알려주세요.',
    type: 'toggle',
    options: ['10대', '20대', '30대', '40대', '50대', '60대 이상'],
    icon: '🎂',
    label: '나이대',
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
    question: '어떤 여행을 하고 싶은지 자유롭게 알려주세요.',
    subQuestion: '좋아하는 장소나 여행 분위기 등을 편하게 말씀해주세요.',
    type: 'text',
    icon: '🍃',
    label: '여행 스타일',
  },
]

export const INITIAL_ANSWERS = STEPS.reduce((acc, s) => ({ ...acc, [s.key]: null }), {})
