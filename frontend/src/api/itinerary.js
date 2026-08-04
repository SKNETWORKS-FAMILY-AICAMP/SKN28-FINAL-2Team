import api from "./axios";

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

  return {
    id: data.id,
    title: data.title,
    subtitle: data.subtitle,
    startDate: data.start_date,
    endDate: data.end_date,
    durationLabel: data.duration_label,
    companionCount: data.companion_count,
    budgetPerPerson: data.budget_per_person,
    totalCost: data.total_cost,
    style: data.style_display,
    costBreakdown: data.cost_breakdown,
<<<<<<< HEAD
    days: data.days.map(day => ({
=======
    days: data.days.map((day) => ({
>>>>>>> e8f9bd0 (feat: 일정 공유 기능 및 리뷰 페이지 API 연동)
      dayNumber: day.day_number,
      date: day.date,
      items: day.items,
    })),
  };
<<<<<<< HEAD
}; 
=======
};

export const getSharedItinerary = async (token) => {
  const { data } = await api.get(
    `/travel/itineraries/shared/${token}/`
  );

  return {
    id: data.id,
    title: data.title,
    subtitle: data.subtitle,
    startDate: data.start_date,
    endDate: data.end_date,
    durationLabel: data.duration_label,
    companionCount: data.companion_count,
    budgetPerPerson: data.budget_per_person,
    totalCost: data.total_cost,
    style: data.style_display,
    costBreakdown: data.cost_breakdown,
    days: data.days.map((day) => ({
      dayNumber: day.day_number,
      date: day.date,
      items: day.items,
    })),
  };
};

export const createShareLink = async (id) => {
  const { data } = await api.post(
    `/travel/itineraries/${id}/share/`
  );

  return data;
};
>>>>>>> e8f9bd0 (feat: 일정 공유 기능 및 리뷰 페이지 API 연동)
