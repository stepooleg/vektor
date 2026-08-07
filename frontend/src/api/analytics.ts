/**
 * API аналитики: дашборд сотрудника (SPEC §9.2, issue #15).
 *
 * Соответствует бэкенду GET /api/v1/analytics/employees/<id>/dashboard/.
 */
import { apiClient } from "./client";

export interface CompetencyProfileRow {
  competency_id: number;
  competency_name: string;
  mean_score: number;
  cycles_count: number;
}

export interface CycleDynamicsRow {
  cycle_id: number;
  cycle_name: string;
  overall_mean: number;
}

export interface EmployeeDashboard {
  employee: {
    id: number;
    full_name: string;
    department: string;
    position: string;
  };
  competency_profile: CompetencyProfileRow[];
  cycle_dynamics: CycleDynamicsRow[];
}

/** Получить дашборд сотрудника (агрегаты, без сырых оценок). */
export async function getEmployeeDashboard(employeeId: number): Promise<EmployeeDashboard> {
  const { data } = await apiClient.get<EmployeeDashboard>(
    `/analytics/employees/${employeeId}/dashboard/`,
  );
  return data;
}
