import axios from "axios";
import { API_BASE_URL } from "./config";

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("accessToken");

  if (token && token !== "null" && token !== "undefined") {
    config.headers.Authorization = `Bearer ${token}`;
  } else {
    delete config.headers.Authorization;
  }

  return config;
});

// bookmarkApi / cartApi / packageApi / reservationApi가 각자 따로 구현하던
// 에러 메시지 추출 로직을 한 곳으로 모은 헬퍼.
// 서버가 detail / message / package_id 형태로 에러를 내려주는 경우를 모두 처리한다.
export const extractErrorMessage = (error, fallbackMessage) => {
  const data = error?.response?.data;

  if (!data) return fallbackMessage;
  if (data.detail) return data.detail;
  if (data.message) return data.message;

  if (data.package_id) {
    return Array.isArray(data.package_id) ? data.package_id[0] : data.package_id;
  }

  return fallbackMessage;
};

export default api;