/**
 * API компетенций (SPEC §4).
 *
 * Соответствует бэкенду GET /api/v1/competencies/* (DRF-роутеры).
 */
import { apiClient } from "./client";

export interface Competency {
  id: number;
  name: string;
  description: string;
  group: number;
  scale: number;
}

export interface CompetencyGroup {
  id: number;
  name: string;
  description: string;
}

interface Paginated<T> {
  count: number;
  results: T[];
}

/** Получить список компетенций. */
export async function getCompetencies(): Promise<Competency[]> {
  const { data } = await apiClient.get<Paginated<Competency>>("/competencies/competencies/");
  return data.results;
}

/** Получить список групп компетенций. */
export async function getCompetencyGroups(): Promise<CompetencyGroup[]> {
  const { data } = await apiClient.get<Paginated<CompetencyGroup>>("/competencies/groups/");
  return data.results;
}
