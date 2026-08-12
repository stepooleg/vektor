/** Сценарии непрерывной обратной связи (SPEC §6.1, issue #69). */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createFeedbackRequest,
  createPraise,
  getFeedbackRecipients,
  getFeedbackRequests,
  getPraises,
} from "@/api/feedback";
import { FeedbackPage } from "./FeedbackPage";

vi.mock("@/api/feedback", () => ({
  getPraises: vi.fn(),
  getFeedbackRequests: vi.fn(),
  getFeedbackRecipients: vi.fn(),
  createPraise: vi.fn(),
  createFeedbackRequest: vi.fn(),
  FEEDBACK_REQUEST_STATUS_LABELS: { pending: "Ожидает ответа" },
}));

const colleague = { id: 2, full_name: "Анна Иванова", department: "Разработка" };

describe("FeedbackPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPraises).mockResolvedValue([]);
    vi.mocked(getFeedbackRequests).mockResolvedValue([]);
    vi.mocked(getFeedbackRecipients).mockResolvedValue([colleague]);
  });

  it("создаёт благодарность и показывает подтверждение", async () => {
    vi.mocked(createPraise).mockResolvedValue({
      id: 10,
      recipient: colleague.id,
      recipient_name: colleague.full_name,
      sender_name: "Пётр Смирнов",
      message: "Спасибо за помощь",
      is_public: true,
      is_anonymous: false,
      created_at: "2026-08-12",
    });
    const user = userEvent.setup();
    render(<FeedbackPage />);

    await user.click(await screen.findByRole("button", { name: "Отправить благодарность" }));
    await user.click(screen.getByLabelText("Получатель"));
    await user.click(await screen.findByText(/Анна Иванова/));
    await user.type(screen.getByLabelText("Текст благодарности"), "Спасибо за помощь");
    await user.click(screen.getByRole("button", { name: "Отправить" }));

    await waitFor(() =>
      expect(createPraise).toHaveBeenCalledWith({
        recipient: colleague.id,
        message: "Спасибо за помощь",
        is_public: true,
        is_anonymous: false,
      }),
    );
    expect(await screen.findByText("Благодарность отправлена")).toBeInTheDocument();
  });

  it("создаёт запрос обратной связи", async () => {
    vi.mocked(createFeedbackRequest).mockResolvedValue({
      id: 11,
      requester_name: "Пётр Смирнов",
      recipient: colleague.id,
      recipient_name: colleague.full_name,
      message: "Дай ОС по презентации",
      status: "pending",
      created_at: "2026-08-12",
    });
    const user = userEvent.setup();
    render(<FeedbackPage />);

    await user.click(await screen.findByRole("button", { name: "Запросить обратную связь" }));
    await user.click(screen.getByLabelText("Коллега"));
    await user.click(await screen.findByText(/Анна Иванова/));
    await user.type(screen.getByLabelText("Контекст запроса"), "Дай ОС по презентации");
    await user.click(screen.getByRole("button", { name: "Отправить запрос" }));

    await waitFor(() =>
      expect(createFeedbackRequest).toHaveBeenCalledWith({
        recipient: colleague.id,
        message: "Дай ОС по презентации",
      }),
    );
    expect(await screen.findByText("Запрос отправлен")).toBeInTheDocument();
  });
});
