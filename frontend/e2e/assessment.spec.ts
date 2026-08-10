import { expect, test, type Page, type Route } from "@playwright/test";

interface MockOptions {
  roles: string[];
  assignments?: unknown[];
  onRequest?: (route: Route, pathname: string) => Promise<boolean>;
}

async function mockAssessmentApi(page: Page, options: MockOptions): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (options.onRequest && (await options.onRequest(route, pathname))) return;
    if (pathname === "/api/v1/auth/me/") {
      await route.fulfill({
        json: {
          email: "user@corp.local",
          name: "Пользователь",
          employee_id: 1,
          roles: options.roles,
          csrfToken: "e2e-csrf",
        },
      });
      return;
    }
    if (pathname === "/api/v1/assessment/assignments/") {
      await route.fulfill({
        json: { count: options.assignments?.length ?? 0, results: options.assignments ?? [] },
      });
      return;
    }
    if (pathname === "/api/v1/assessment/cycles/") {
      await route.fulfill({ json: { count: 0, results: [] } });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: "E2E mock: endpoint не настроен" } });
  });
}

test("сотрудник проходит назначенную оценку", async ({ page }) => {
  let submitted: unknown = null;
  await mockAssessmentApi(page, {
    roles: ["employee"],
    assignments: [
      {
        id: 7,
        cycle: 1,
        cycle_name: "Оценка команды",
        deadline: "2026-08-24",
        participant_name: "Иван Иванов",
        group: "peer",
        completed: false,
        competencies: [
          {
            id: 5,
            name: "Командная работа",
            description: "Работает в команде",
            min_value: 1,
            max_value: 5,
          },
        ],
      },
    ],
    onRequest: async (route, pathname) => {
      if (pathname === "/api/v1/assessment/assignments/7/submit/") {
        submitted = route.request().postDataJSON();
        await route.fulfill({ json: { completed: true } });
        return true;
      }
      return false;
    },
  });

  await page.goto("/assessment");
  await page.getByRole("button", { name: "Пройти оценку" }).click();
  await page.getByRole("radio", { name: "4" }).click();
  await page.getByLabel("Общий комментарий").fill("Хороший результат");
  await page.getByRole("button", { name: "Отправить оценку" }).click();

  await expect(page.getByText("Оценка отправлена")).toBeVisible();
  expect(submitted).toEqual({
    responses: [{ competency_id: 5, score: 4, comment: "" }],
    general_comment: "Хороший результат",
  });
  await expect(page.getByRole("button", { name: "Создать цикл" })).toHaveCount(0);
});

test("руководитель создаёт цикл только для доступной команды", async ({ page }) => {
  let created: unknown = null;
  await mockAssessmentApi(page, {
    roles: ["manager"],
    onRequest: async (route, pathname) => {
      if (pathname === "/api/v1/assessment/cycles/setup-options/") {
        await route.fulfill({
          json: {
            frameworks: [{ id: 3, name: "Корпоративная модель" }],
            participants: [{ id: 11, full_name: "Иван Иванов", department: "Разработка" }],
          },
        });
        return true;
      }
      if (pathname === "/api/v1/assessment/cycles/" && route.request().method() === "POST") {
        created = route.request().postDataJSON();
        await route.fulfill({
          status: 201,
          json: {
            id: 9,
            name: "Оценка команды",
            status: "assigned",
            anonymity_threshold: 3,
            start_date: "2026-08-11",
            deadline: "2026-08-24",
            created_at: "2026-08-10",
            participants_count: 1,
          },
        });
        return true;
      }
      return false;
    },
  });

  await page.goto("/assessment");
  await page.getByRole("button", { name: "Создать цикл" }).click();
  await page.getByLabel("Название цикла").fill("Оценка команды");
  await page.getByLabel("Модель компетенций").click();
  await page.getByText("Корпоративная модель", { exact: true }).click();
  await page.getByLabel("Участники").click();
  await page.getByText(/Иван Иванов/).click();
  await page.getByLabel("Дата начала").fill("2026-08-11");
  await page.getByLabel("Дедлайн").fill("2026-08-24");
  await page.getByRole("button", { name: "Создать", exact: true }).click();

  await expect(page.getByText("Цикл создан, оценщики назначены.")).toBeVisible();
  expect(created).toMatchObject({
    name: "Оценка команды",
    framework: 3,
    participant_ids: [11],
  });
});
