/**
 * API циклов оценки (SPEC §5, §14.2, issue #17).
 *
 * Соответствует бэкенду /api/v1/assessment/.
 */
import { apiClient } from "./client";

export interface AssessmentCycle {
  id: number;
  name: string;
  status: string;
  anonymity_threshold: number;
  start_date: string | null;
  deadline: string | null;
  created_at: string;
}

export interface GroupResult {
  group: string;
  participants_count: number;
  mean_score: number;
  hidden_by_threshold: boolean;
}

export interface CycleResults {
  cycle_id: number;
  groups: GroupResult[];
}

interface Paginated<T> {
  count: number;
  results: T[];
}

/** Получить список циклов оценки. */
export async function getCycles(): Promise<AssessmentCycle[]> {
  const { data } = await apiClient.get<Paginated<AssessmentCycle>>("/assessment/cycles/");
  return data.results;
}

/** Получить агрегированные результаты цикла (без сырых данных). */
export async function getCycleResults(cycleId: number): Promise<CycleResults> {
  const { data } = await apiClient.get<CycleResults>(`/assessment/cycles/${cycleId}/results/`);
  return data;
}

/** Человекочитаемые названия статусов цикла (SPEC §5.2). */
export const CYCLE_STATUS_LABELS: Record<string, string> = {
  created: "Создан",
  assigned: "Оценщики назначены",
  in_progress: "Идёт оценка",
  collecting: "Сбор ответов завершается",
  aggregated: "Результаты рассчитаны",
  closed: "Закрыт",
};

/** Лейблы групп оценщиков для отображения результатов. */
export const GROUP_LABELS: Record<string, string> = {
  manager: "Руководитель",
  peer: "Коллеги",
  subordinate: "Подчинённые",
  self: "Самооценка",
};
