/**
 * API обратной связи и портфолио (SPEC §6.1, §6.2, issue #34).
 */
import { apiClient } from "./client";

export interface Praise {
  id: number;
  recipient_name: string;
  sender_name: string | null;
  message: string;
  is_public: boolean;
  is_anonymous: boolean;
  created_at: string;
}

export interface PortfolioEntry {
  id: number;
  type: string;
  title: string;
  description: string;
  created_at: string;
}

interface Paginated<T> {
  count: number;
  results: T[];
}

export async function getPraises(): Promise<Praise[]> {
  const { data } = await apiClient.get<Paginated<Praise>>("/feedback/praises/");
  return data.results;
}

export async function getPortfolioEntries(): Promise<PortfolioEntry[]> {
  const { data } = await apiClient.get<Paginated<PortfolioEntry>>("/portfolio/entries/");
  return data.results;
}

export const PORTFOLIO_TYPE_LABELS: Record<string, string> = {
  course_passed: "Курс пройдён",
  achievement: "Достижение",
  project: "Проект",
  thank_you: "Благодарность",
};
