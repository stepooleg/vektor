/**
 * Точка входа приложения Vektor (issue #2, #24 PWA).
 *
 * Монтирует <App/> в #root, подключает глобальные стили (токены, шрифт, темы),
 * регистрирует Service Worker для PWA и push-уведомлений (SPEC §10.4).
 */
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "@/app/App";
import "@/styles/global.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Элемент #root не найден — проверьте index.html");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Регистрация Service Worker (PWA + push, SPEC §10.4).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      // SW-ошибки не блокируют приложение — логируем.
      console.warn("Service Worker registration failed:", err);
    });
  });
}
