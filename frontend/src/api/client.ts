/**
 * API-клиент Vektor (axios).
 *
 * Базовый URL из VITE_API_BASE_URL (по умолчанию /api/v1). Сессионная
 * аутентификация (cookie sessionid) — credentials: include.
 * Единая обработка ошибок → ApiError.
 */
import axios, { type AxiosInstance, type AxiosError } from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

/** Структура ошибки API (деталь от DRF). */
export interface ApiError {
  /** HTTP-статус или 0 при сетевом сбое. */
  status: number;
  /** Человекечкое сообщение (detail из DRF или сетевая ошибка). */
  detail: string;
}

/** Синглтон axios-инстанс с сессионной аутентификацией. */
export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

/** Преобразовать ошибку axios в доменный ApiError. */
export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<{ detail?: string }>;
    const detail =
      axiosErr.response?.data?.detail ?? axiosErr.message ?? "Неизвестная ошибка запроса";
    return { status: axiosErr.response?.status ?? 0, detail };
  }
  return { status: 0, detail: "Сетевая ошибка. Проверьте подключение." };
}
