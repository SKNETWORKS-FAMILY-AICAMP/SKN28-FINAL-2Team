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

  status: data.status,
  statusDisplay: data.status_display,

  style: data.style_display,
  styleCode: data.style,
  styleDisplay: data.style_display,

  bookedProductType: data.booked_product_type,
  bookedPackageDbId: data.booked_package_db_id,
  bookedPrice: data.booked_price,
  hotel: data.hotel || null,

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
    companionTypeDisplay: item.companion_type_display,
    companionCount: item.companion_count,
    styleDisplay: item.style_display,
    status: item.status,
    statusDisplay: item.status_display,

    bookedProductType: item.booked_product_type,
    bookedPackageDbId: item.booked_package_db_id,
    bookedPrice: item.booked_price,

    hotel: item.hotel || null,
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

// 일정 수정(채팅) — mode: "edit" | "recommend" | "no_change"
export const reviseItinerary = async (id, message) => {
  const { data } = await api.post(
    `/travel/itineraries/${id}/revise/`,
    {
      message,
    }
  );

  if (data.mode === "recommend") {
    return {
      mode: "recommend",
      message: data.message,
      options: data.options ?? [],
    };
  }

  if (data.mode === "no_change") {
    return {
      mode: "no_change",
      message: data.message,
    };
  }

  return {
    mode: "edit",
    itinerary: mapItinerary(data),
  };
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
// 일정 삭제
export const deleteItinerary = async (id) => {
  await api.delete(`/travel/itineraries/${id}/`);
};

// 일정 확정
export const confirmItinerary = async (id) => {
  const { data } = await api.post(
    `/travel/itineraries/${id}/confirm/`
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

// 실제 자동차 도로 경로 조회
// 동일 일정에 대한 동시 중복 요청 방지
// 실제 자동차 도로 경로 조회
// 동일 경로에 대한 동시 중복 요청 방지
const roadRouteRequests = new Map();

export const getRoadRoute = async (id, packageId = null) => {
  const key = packageId
    ? `${id}:package:${packageId}`
    : `${id}:custom`;

  if (roadRouteRequests.has(key)) {
    return roadRouteRequests.get(key);
  }

  const request = api
    .get(`/travel/itineraries/${id}/road-route/`, {
      params: packageId
        ? { package_id: packageId }
        : {},
    })
    .then(({ data }) => data)
    .finally(() => {
      roadRouteRequests.delete(key);
    });

  roadRouteRequests.set(key, request);

  return request;
};

// 생성된 일정 기반 패키지 추천 조회
const packageRecommendationRequests = new Map();

export const getPackageRecommendations = async (id, topK = 3) => {
  const { data } = await api.get(
    `/travel/itineraries/${id}/package-recommendations/`,
    {
      params: {
        top_k: topK,
      },
    }
  )

  return data
}