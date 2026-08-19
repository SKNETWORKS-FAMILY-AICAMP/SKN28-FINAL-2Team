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

export function extractErrorMessage(error, fallbackMessage) {
  const data = error?.response?.data;

  if (data?.detail) return data.detail;
  if (data?.message) return data.message;
  if (data?.package_id) {
    return Array.isArray(data.package_id) ? data.package_id[0] : data.package_id;
  }

  return fallbackMessage;
}

export default api;
