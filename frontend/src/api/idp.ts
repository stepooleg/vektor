/**
 * API индивидуального плана развития (SPEC §8, issue #26).
 *
 * BE API для ИПР ещё не подключён публично (модели+сервисы готовы в #23);
 * здесь — клиент на основе ожидаемой структуры. Подключение viewsets —
 * следующий шаг; сейчас данные можно получить через admin/django shell.
 */
import { apiClient } from "./client";

export interface DevAction {
  id: number;
  type: string;
  title: string;
  status: string;
  due_date: string | null;
  course: number | null;
  mentor: number | null;
}

export interface DevGoal {
  id: number;
  title: string;
  competency: number;
  target_level: number;
  actions: DevAction[];
}

export interface DevelopmentPlan {
  id: number;
  title: string;
  status: string;
  goals: DevGoal[];
}

interface Paginated<T> {
  count: number;
  results: T[];
}

/** Получить список планов развития. */
export async function getDevelopmentPlans(): Promise<DevelopmentPlan[]> {
  const { data } = await apiClient.get<Paginated<DevelopmentPlan>>("/idp/plans/");
  return data.results;
}

/** Лейблы статусов ИПР (SPEC §8.2, §8.3). */
export const PLAN_STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  approved: "Согласован",
  in_progress: "В работе",
  completed: "Завершён",
};

/** Лейблы статусов действий (SPEC §8.2). */
export const ACTION_STATUS_LABELS: Record<string, string> = {
  planned: "Запланировано",
  in_progress: "В работе",
  completed: "Завершено",
  overdue: "Просрочено",
};

/** Лейблы типов действий (SPEC §8.2). */
export const ACTION_TYPE_LABELS: Record<string, string> = {
  course: "Курс",
  task: "Задание",
  mentoring: "Менторство",
  reading: "Чтение",
  practice: "Практика",
};
