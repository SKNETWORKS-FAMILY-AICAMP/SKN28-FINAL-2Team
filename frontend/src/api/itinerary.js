import api from "./axios";

const mapItinerary = (data) => ({
  id: data.id,
  title: data.title,
  subtitle: data.subtitle,
  startDate: data.start_date,
  endDate: data.end_date,
  durationLabel: data.duration_label,

  companionType: data.companion_type,
  companionTypeDisplay: data.companion_type_display,
  companionCount: data.companion_count,

  transport: data.transport,
  transportDisplay: data.transport_display,

  style: data.style_display,
  styleCode: data.style,
  styleDisplay: data.style_display,

  budgetPerPerson: data.budget_per_person,
  totalCost: data.total_cost,
  costBreakdown: data.cost_breakdown,

  days: data.days.map((day) => ({
    dayNumber: day.day_number,
    date: day.date,
    items: day.items,
  })),
});

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

export const getItinerary = async (id) => {
  const { data } = await api.get(`/travel/itineraries/${id}/`);

  return mapItinerary(data);
};

export const createItinerary = async (data) => {
  const { data: response } = await api.post(
    "/travel/itineraries/",
    data
  );

  return mapItinerary(response);
};

export const regenerateItinerary = async (id) => {
  const { data } = await api.post(
    `/travel/itineraries/${id}/regenerate/`
  );

  return mapItinerary(data);
};

export const getSharedItinerary = async (token) => {
  const { data } = await api.get(
    `/travel/itineraries/shared/${token}/`
  );

  return mapItinerary(data);
};

export const createShareLink = async (id) => {
  const { data } = await api.post(
    `/travel/itineraries/${id}/share/`
  );

  return data;
};

export const deleteItinerary = async (id) => {
  await api.delete(`/travel/itineraries/${id}/`);
};

// 일정 일부 수정
export const patchItinerary = async (id, payload) => {
  const { data } = await api.patch(
    `/travel/itineraries/${id}/`,
    payload
  );

  return mapItinerary(data);
};

// 여행 경로 조회
export const getRoute = async (id) => {
  const { data } = await api.get(
    `/travel/itineraries/${id}/route/`
  );

  return data;
};