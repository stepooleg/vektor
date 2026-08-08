/**
 * API модуля обучения LMS (SPEC §7, issue #25).
 *
 * Соответствует бэкенду /api/v1/lms/.
 */
import { apiClient } from "./client";

export interface Course {
  id: number;
  title: string;
  description: string;
  category: number | null;
  status: string;
  is_mandatory: boolean;
  pass_threshold: number;
  created_at: string;
}

export interface CourseCategory {
  id: number;
  name: string;
  parent: number | null;
}

interface Paginated<T> {
  count: number;
  results: T[];
}

export interface CourseFilter {
  search?: string;
  category?: number;
  competency?: number;
  is_mandatory?: boolean;
}

/** Получить список курсов с фильтрами (SPEC §7.1). */
export async function getCourses(filter: CourseFilter = {}): Promise<Course[]> {
  const params: Record<string, string | number | boolean> = {};
  if (filter.search) params.search = filter.search;
  if (filter.category) params.category = filter.category;
  if (filter.competency) params.competency = filter.competency;
  if (filter.is_mandatory !== undefined) params.is_mandatory = filter.is_mandatory;
  const { data } = await apiClient.get<Paginated<Course>>("/lms/courses/", { params });
  return data.results;
}

/** Получить список категорий каталога. */
export async function getCourseCategories(): Promise<CourseCategory[]> {
  const { data } = await apiClient.get<Paginated<CourseCategory>>("/lms/categories/");
  return data.results;
}

/** Лейблы статусов курса (SPEC §7.3). */
export const COURSE_STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  published: "Опубликован",
  archived: "В архиве",
};
