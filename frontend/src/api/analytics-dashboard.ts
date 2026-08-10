/**
 * API дашборда компании (SPEC §9.1, issue #35).
 */
import { apiClient } from "./client";

export interface CompanyDashboard {
  total_employees: number;
  assessed_employees: number;
  assessment_coverage: number;
  average_score: number;
  total_cycles: number;
}

export async function getCompanyDashboard(): Promise<CompanyDashboard> {
  const { data } = await apiClient.get<CompanyDashboard>("/analytics/company-dashboard/");
  return data;
}
