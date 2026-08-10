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
  lessons: Lesson[];
}

export interface AnswerOption {
  id: number;
  text: string;
  order: number;
}

export interface Question {
  id: number;
  text: string;
  type: "single" | "multiple" | "scale" | "text";
  order: number;
  options: AnswerOption[];
}

export interface Lesson {
  id: number;
  title: string;
  type: "text" | "quiz";
  order: number;
  content: string;
  pass_score: number;
  max_attempts: number;
  questions: Question[];
}

export interface CourseSummary {
  id: number;
  title: string;
  description: string;
  is_mandatory: boolean;
  pass_threshold: number;
}

export interface LessonProgress {
  lesson: number;
  completed: boolean;
  best_score: number;
  attempts_used: number;
}

export interface Certificate {
  code: string;
  employee_full_name: string;
  course_title: string;
  issued_at: string;
}

export interface Enrollment {
  id: number;
  course: CourseSummary;
  status: string;
  progress_percent: number;
  enrolled_at: string;
  completed_at: string | null;
  lesson_progresses: LessonProgress[];
  certificate: Certificate | null;
}

export interface QuizResult {
  result: { percent: number; passed: boolean };
  enrollment: Enrollment;
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

/** Получить программу и материалы опубликованного курса. */
export async function getCourse(courseId: number): Promise<Course> {
  const { data } = await apiClient.get<Course>(`/lms/courses/${courseId}/`);
  return data;
}

/** Получить список категорий каталога. */
export async function getCourseCategories(): Promise<CourseCategory[]> {
  const { data } = await apiClient.get<Paginated<CourseCategory>>("/lms/categories/");
  return data.results;
}

/** Получить личные записи и прогресс обучения. */
export async function getMyLearning(): Promise<Enrollment[]> {
  const { data } = await apiClient.get<Enrollment[]>("/lms/courses/my/");
  return data;
}

/** Записаться на опубликованный курс. */
export async function enrollInCourse(courseId: number): Promise<Enrollment> {
  const { data } = await apiClient.post<Enrollment>(`/lms/courses/${courseId}/enroll/`);
  return data;
}

/** Отметить текстовый урок прочитанным. */
export async function completeLesson(courseId: number, lessonId: number): Promise<Enrollment> {
  const { data } = await apiClient.post<Enrollment>(
    `/lms/courses/${courseId}/lessons/${lessonId}/complete/`,
  );
  return data;
}

/** Отправить ответы теста на автоматическую проверку. */
export async function submitQuiz(
  courseId: number,
  lessonId: number,
  answers: Record<number, number[]>,
): Promise<QuizResult> {
  const { data } = await apiClient.post<QuizResult>(
    `/lms/courses/${courseId}/lessons/${lessonId}/submit-quiz/`,
    { answers },
  );
  return data;
}

/** Лейблы статусов курса (SPEC §7.3). */
export const COURSE_STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  published: "Опубликован",
  archived: "В архиве",
};

export const ENROLLMENT_STATUS_LABELS: Record<string, string> = {
  not_started: "Не начат",
  in_progress: "В процессе",
  completed: "Пройдён",
};
