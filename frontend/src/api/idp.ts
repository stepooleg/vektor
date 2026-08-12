/** API редактирования и прогресса ИПР (SPEC §8, issue #73). */
import { apiClient } from "./client";

export interface DevAction {
  id: number;
  goal: number;
  type: string;
  title: string;
  status: string;
  progress_percent: number;
  due_date: string | null;
  course: number | null;
  mentor: number | null;
}

export type GoalSource =
  | { type: "manual" }
  | {
      type: "assessment";
      cycle_id: number;
      cycle_name: string;
      current_level: number;
      expected_level: number;
    };

export interface DevGoal {
  id: number;
  plan: number;
  title: string;
  description: string;
  competency: number;
  target_level: number;
  source: GoalSource;
  actions: DevAction[];
}

export interface DevelopmentPlan {
  id: number;
  employee: number;
  employee_name: string;
  title: string;
  status: string;
  progress_percent: number;
  goals: DevGoal[];
}

export interface IdpOptions {
  employees: { id: number; name: string }[];
  cycles: { id: number; name: string }[];
  competencies: { id: number; name: string }[];
}

interface Paginated<T> {
  count: number;
  results: T[];
}

export async function getDevelopmentPlans(): Promise<DevelopmentPlan[]> {
  const { data } = await apiClient.get<Paginated<DevelopmentPlan>>("/idp/plans/");
  return data.results;
}

export async function getIdpOptions(): Promise<IdpOptions> {
  const { data } = await apiClient.get<IdpOptions>("/idp/plans/options/");
  return data;
}

export async function createDevelopmentPlan(payload: {
  employee: number;
  title: string;
}): Promise<DevelopmentPlan> {
  const { data } = await apiClient.post<DevelopmentPlan>("/idp/plans/", payload);
  return data;
}

export async function autoGeneratePlan(employee: number, cycle: number): Promise<DevelopmentPlan> {
  const { data } = await apiClient.post<DevelopmentPlan>("/idp/plans/auto-generate/", {
    employee,
    cycle,
  });
  return data;
}

export async function updateDevelopmentPlan(
  id: number,
  payload: Partial<Pick<DevelopmentPlan, "title" | "status">>,
): Promise<DevelopmentPlan> {
  const { data } = await apiClient.patch<DevelopmentPlan>(`/idp/plans/${id}/`, payload);
  return data;
}

export async function createDevGoal(payload: {
  plan: number;
  competency: number;
  title: string;
  description?: string;
  target_level: number;
}): Promise<DevGoal> {
  const { data } = await apiClient.post<DevGoal>("/idp/goals/", payload);
  return data;
}

export async function deleteDevGoal(id: number): Promise<void> {
  await apiClient.delete(`/idp/goals/${id}/`);
}

export async function createDevAction(payload: {
  goal: number;
  type: string;
  title: string;
  due_date?: string;
}): Promise<DevAction> {
  const { data } = await apiClient.post<DevAction>("/idp/actions/", payload);
  return data;
}

export async function updateDevAction(
  id: number,
  payload: Partial<Pick<DevAction, "title" | "status" | "progress_percent" | "due_date">>,
): Promise<DevAction> {
  const { data } = await apiClient.patch<DevAction>(`/idp/actions/${id}/`, payload);
  return data;
}

export async function deleteDevAction(id: number): Promise<void> {
  await apiClient.delete(`/idp/actions/${id}/`);
}

export const PLAN_STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  approved: "Согласован",
  in_progress: "В работе",
  completed: "Завершён",
};

export const ACTION_STATUS_LABELS: Record<string, string> = {
  planned: "Запланировано",
  in_progress: "В работе",
  completed: "Завершено",
  overdue: "Просрочено",
};

export const ACTION_TYPE_LABELS: Record<string, string> = {
  course: "Курс",
  task: "Задание",
  mentoring: "Менторство",
  reading: "Чтение",
  practice: "Практика",
};
