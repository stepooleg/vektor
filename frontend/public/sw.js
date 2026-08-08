/**
 * Vektor Service Worker (PWA, SPEC §10.4).
 *
 * Минимальный SW: обработка push-событий и кликов по уведомлениям.
 * Кеширование офлайн (Workbox) добавляется позже — сейчас фокус на push.
 */

// Показ push-уведомления (SPEC §10.4).
self.addEventListener("push", (event) => {
  let payload = { title: "Vektor", body: "Новое уведомление" };
  try {
    if (event.data) {
      payload = event.data.json();
    }
  } catch {
    // payload не JSON — игнорируем, показываем дефолт.
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || "Vektor", {
      body: payload.body || "",
      icon: "/icon-192.png",
      badge: "/icon-192.png",
    }),
  );
});

// Клики по уведомлению → фокус на окно приложения.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow("/");
      }
      return undefined;
    }),
  );
});
