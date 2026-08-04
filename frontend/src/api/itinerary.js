import api from "./axios";


// 공통 변환 함수
const mapItinerary = (data) => ({
  id: data.id,
  title: data.title,
  subtitle: data.subtitle,
  startDate: data.start_date,
  endDate: data.end_date,
  durationLabel: data.duration_label,
  companionCount: data.companion_count,
  budgetPerPerson: data.budget_per_person,
  totalCost: data.total_cost,
  style: data.style,
  styleDisplay: data.style_display,
  costBreakdown: data.cost_breakdown,
  days: data.days.map((day) => ({
    dayNumber: day.day_number,
    date: day.date,
    items: day.items,
  })),
});


// 일정 목록 조회
export const getItineraries = async () => {
  const { data } = await api.get("/travel/itineraries/");

  return data.map((item) => ({
    id: item.id,
    title: item.title,
    subtitle: item.subtitle,
    startDate: item.start_date,
    endDate: item.end_date,
    durationLabel: item.duration_label,
    companionCount: item.companion_count,
    totalCost: item.total_cost,
    status: item.status,
    statusDisplay: item.status_display,
  }));
};

// 일정 상세 조회
export const getItinerary = async (id) => {
  const { data } = await api.get(`/travel/itineraries/${id}/`);
  return mapItinerary(data);
};


// 일정 생성
export const createItinerary = async (payload) => {
  const { data } = await api.post("/travel/itineraries/", payload);
  return mapItinerary(data);
};

// 일정 재생성
export const regenerateItinerary = async (id) => {
  const { data } = await api.post(
    `/travel/itineraries/${id}/regenerate/`
  );

  return mapItinerary(data);
};

// 일정 수정(채팅)
export const reviseItinerary = async (id, message) => {
  const { data } = await api.post(
    `/travel/itineraries/${id}/revise/`,
    {
      message,
    }
  );

  return mapItinerary(data);
};

// 공유 일정 조회
export const getSharedItinerary = async (token) => {
  const { data } = await api.get(
    `/travel/itineraries/shared/${token}/`
  );

  return mapItinerary(data);
};


// 공유 링크 생성
export const createShareLink = async (id) => {
  const { data } = await api.post(
    `/travel/itineraries/${id}/share/`
  );

  return data;
};


// 일정 전체 수정
export const updateItinerary = async (id, payload) => {
  const { data } = await api.put(
    `/travel/itineraries/${id}/`,
    payload
  );

  return mapItinerary(data);
};


// 일정 일부 수정

export const patchItinerary = async (id, payload) => {
  const { data } = await api.patch(
    `/travel/itineraries/${id}/`,
    payload
  );

  return mapItinerary(data);
};


 
//  일정 삭제
export const deleteItinerary = async (id) => {
  await api.delete(`/travel/itineraries/${id}/`);
};


//  여행 경로 조회
export const getRoute = async (id) => {
  const { data } = await api.get(
    `/travel/itineraries/${id}/route/`
  );
};