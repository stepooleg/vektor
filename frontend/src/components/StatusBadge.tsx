/**
 * Бейдж статуса (BRANDBOOK §6.8 — статусы ИПР/курсов/циклов).
 *
 * Цвета — через дизайн-токены, без хардкод-HEX (BRANDBOOK §10.2).
 * «Запланировано» — нейтральный; «Активен/В работе» — Primary;
 * «Завершено/Пройдено» — Accent; «Просрочено/Закрыто» — Error/нейтральный.
 */
import "./status-badge.css";

interface StatusBadgeProps {
  /** Ключ статуса (из бэкенда). */
  status: string;
  /** Лейбл для отображения. */
  label: string;
}

/** Класс цвета бейджа по категории статуса (BRANDBOOK §6.8). */
function statusCategory(status: string): string {
  if (["in_progress", "collecting", "assigned", "active"].includes(status)) {
    return "primary";
  }
  if (["aggregated", "completed", "passed"].includes(status)) {
    return "accent";
  }
  if (["overdue", "failed"].includes(status)) {
    return "error";
  }
  return "neutral"; // created, closed, planned
}

export function StatusBadge({ status, label }: StatusBadgeProps): React.JSX.Element {
  const category = statusCategory(status);
  return <span className={`vektor-status-badge vektor-status-badge--${category}`}>{label}</span>;
}
