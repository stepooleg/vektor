/**
 * API push-подписок (SPEC §10.4, issue #24).
 *
 * Запрос публичного VAPID-ключа и регистрация подписки на сервере.
 */
import { apiClient } from "./client";

export interface VapidKeyResponse {
  public_key: string;
}

/** Получить публичный VAPID-ключ (для подписки в браузере). */
export async function getVapidPublicKey(): Promise<string> {
  const { data } = await apiClient.get<VapidKeyResponse>("/notifications/vapid-public/");
  return data.public_key;
}

/** Зарегистрировать push-подписку на сервере. */
export async function subscribeToPush(subscription: PushSubscription): Promise<void> {
  const subJson = subscription.toJSON();
  await apiClient.post("/notifications/subscribe/", subJson);
}

/**
 * Запросить разрешение и подписать пользователя на push (SPEC §10.4).
 *
 * Возвращает true при успехе, false при отказе/недоступности.
 */
export async function requestPushPermission(): Promise<boolean> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return false;
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return false;
  }
  const publicKey = await getVapidPublicKey();
  if (!publicKey) {
    return false;
  }
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
  });
  await subscribeToPush(subscription);
  return true;
}

/** Декодировать VAPID public key (base64url → Uint8Array для PushManager). */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const output = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    output[i] = rawData.charCodeAt(i);
  }
  return output;
}
