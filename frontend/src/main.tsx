/**
 * Точка входа приложения Vektor (issue #2).
 *
 * Монтирует <App/> в #root, подключает глобальные стили (токены, шрифт, темы).
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
