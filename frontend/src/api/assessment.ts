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
  participants_count?: number;
}

export interface SetupOptions {
  frameworks: Array<{ id: number; name: string }>;
  participants: Array<{ id: number; full_name: string; department: string }>;
}

export interface CreateCyclePayload {
  name: string;
  framework: number;
  participant_ids: number[];
  start_date: string;
  deadline: string;
  anonymity_threshold: number;
}

export interface AssignmentCompetency {
  id: number;
  name: string;
  description: string;
  min_value: number;
  max_value: number;
}

export interface ReviewerAssignment {
  id: number;
  cycle: number;
  cycle_name: string;
  deadline: string | null;
  participant_name: string;
  group: string;
  completed: boolean;
  competencies: AssignmentCompetency[];
}

export interface AssignmentSubmitPayload {
  responses: Array<{ competency_id: number; score: number; comment: string }>;
  general_comment: string;
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

/** Доступные пользователю модели и участники мастера. */
export async function getSetupOptions(): Promise<SetupOptions> {
  const { data } = await apiClient.get<SetupOptions>("/assessment/cycles/setup-options/");
  return data;
}

/** Создать цикл вместе с участниками и автоматическими назначениями. */
export async function createCycle(payload: CreateCyclePayload): Promise<AssessmentCycle> {
  const { data } = await apiClient.post<AssessmentCycle>("/assessment/cycles/", payload);
  return data;
}

/** Запустить подготовленный цикл. */
export async function startCycle(cycleId: number): Promise<AssessmentCycle> {
  const { data } = await apiClient.post<AssessmentCycle>(`/assessment/cycles/${cycleId}/start/`);
  return data;
}

/** Получить задания только текущего оценщика. */
export async function getMyAssignments(): Promise<ReviewerAssignment[]> {
  const { data } = await apiClient.get<Paginated<ReviewerAssignment>>("/assessment/assignments/");
  return data.results;
}

/** Одноразово отправить заполненный опросник. */
export async function submitAssignment(
  assignmentId: number,
  payload: AssignmentSubmitPayload,
): Promise<{ completed: true }> {
  const { data } = await apiClient.post<{ completed: true }>(
    `/assessment/assignments/${assignmentId}/submit/`,
    payload,
  );
  return data;
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
