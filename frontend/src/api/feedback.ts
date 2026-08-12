/**
 * API обратной связи и портфолио (SPEC §6.1, §6.2, issue #34).
 */
import { apiClient } from "./client";

export interface Praise {
  id: number;
  recipient: number;
  recipient_name: string;
  sender_name: string | null;
  message: string;
  is_public: boolean;
  is_anonymous: boolean;
  created_at: string;
}

export interface FeedbackRequest {
  id: number;
  requester_name: string;
  recipient: number;
  recipient_name: string;
  message: string;
  status: string;
  created_at: string;
}

export interface FeedbackRecipient {
  id: number;
  full_name: string;
  department: string;
}

export interface PortfolioEntry {
  id: number;
  employee_name: string;
  type: string;
  title: string;
  description: string;
  created_at: string;
}

export interface PortfolioTarget extends FeedbackRecipient {
  is_self: boolean;
}

interface Paginated<T> {
  count: number;
  results: T[];
}

export async function getPraises(): Promise<Praise[]> {
  const { data } = await apiClient.get<Paginated<Praise>>("/feedback/praises/");
  return data.results;
}

export async function getFeedbackRequests(): Promise<FeedbackRequest[]> {
  const { data } = await apiClient.get<Paginated<FeedbackRequest>>("/feedback/requests/");
  return data.results;
}

export async function getFeedbackRecipients(): Promise<FeedbackRecipient[]> {
  const { data } = await apiClient.get<FeedbackRecipient[]>("/feedback/requests/recipients/");
  return data;
}

export interface CreatePraisePayload {
  recipient: number;
  message: string;
  is_public: boolean;
  is_anonymous: boolean;
}

export async function createPraise(payload: CreatePraisePayload): Promise<Praise> {
  const { data } = await apiClient.post<Praise>("/feedback/praises/", payload);
  return data;
}

export async function createFeedbackRequest(payload: {
  recipient: number;
  message: string;
}): Promise<FeedbackRequest> {
  const { data } = await apiClient.post<FeedbackRequest>("/feedback/requests/", payload);
  return data;
}

export async function getPortfolioEntries(): Promise<PortfolioEntry[]> {
  const { data } = await apiClient.get<Paginated<PortfolioEntry>>("/portfolio/entries/");
  return data.results;
}

export async function getPortfolioTargets(): Promise<PortfolioTarget[]> {
  const { data } = await apiClient.get<PortfolioTarget[]>("/portfolio/entries/targets/");
  return data;
}

export interface CreatePortfolioEntryPayload {
  employee: number;
  type: "achievement" | "project";
  title: string;
  description: string;
}

export async function createPortfolioEntry(
  payload: CreatePortfolioEntryPayload,
): Promise<PortfolioEntry> {
  const { data } = await apiClient.post<PortfolioEntry>("/portfolio/entries/", payload);
  return data;
}

export const PORTFOLIO_TYPE_LABELS: Record<string, string> = {
  course_passed: "Курс пройдён",
  achievement: "Достижение",
  project: "Проект",
  thank_you: "Благодарность",
};

export const FEEDBACK_REQUEST_STATUS_LABELS: Record<string, string> = {
  pending: "Ожидает ответа",
  answered: "Отвечено",
  expired: "Просрочено",
};
