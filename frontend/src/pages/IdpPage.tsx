/** Модуль ИПР: автоподбор, ручная правка и прогресс (SPEC §14.4, issue #73). */
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useState } from "react";

import {
  ACTION_STATUS_LABELS,
  ACTION_TYPE_LABELS,
  PLAN_STATUS_LABELS,
  autoGeneratePlan,
  createDevAction,
  createDevGoal,
  createDevelopmentPlan,
  deleteDevAction,
  deleteDevGoal,
  getDevelopmentPlans,
  getIdpOptions,
  updateDevAction,
  updateDevelopmentPlan,
  type DevGoal,
  type DevelopmentPlan,
  type IdpOptions,
} from "@/api/idp";
import { toApiError } from "@/api/client";
import { useAuth } from "@/app/auth-context";
import { StatusBadge } from "@/components/StatusBadge";

const { Title, Text } = Typography;
const NEXT_PLAN_STATUS: Record<string, string> = {
  draft: "approved",
  approved: "in_progress",
  in_progress: "completed",
};
const PROGRESS_OPTIONS = [0, 25, 50, 75, 100].map((value) => ({
  value,
  label: `${value}%`,
}));

type Dialog = "manual-plan" | "auto-plan" | "goal" | "action" | null;

export function IdpPage(): React.JSX.Element {
  const { user } = useAuth();
  const [plans, setPlans] = useState<DevelopmentPlan[]>([]);
  const [options, setOptions] = useState<IdpOptions | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [selectedPlan, setSelectedPlan] = useState<number | null>(null);
  const [selectedGoal, setSelectedGoal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form] = Form.useForm();
  const canEdit = user?.roles.some((role) => role === "manager" || role === "hr") ?? false;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedPlans, loadedOptions] = await Promise.all([
        getDevelopmentPlans(),
        canEdit ? getIdpOptions() : Promise.resolve(null),
      ]);
      setPlans(loadedPlans);
      setOptions(loadedOptions);
    } catch (caught) {
      setError(toApiError(caught).detail);
    } finally {
      setLoading(false);
    }
  }, [canEdit]);

  useEffect(() => {
    void load();
  }, [load]);

  function openDialog(next: Dialog, planId?: number, goalId?: number): void {
    form.resetFields();
    setSelectedPlan(planId ?? null);
    setSelectedGoal(goalId ?? null);
    setDialog(next);
    setError(null);
    setNotice(null);
  }

  async function submit(values: Record<string, string | number>): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      if (dialog === "manual-plan") {
        await createDevelopmentPlan({
          employee: Number(values.employee),
          title: String(values.title),
        });
      } else if (dialog === "auto-plan") {
        await autoGeneratePlan(Number(values.employee), Number(values.cycle));
      } else if (dialog === "goal" && selectedPlan !== null) {
        await createDevGoal({
          plan: selectedPlan,
          competency: Number(values.competency),
          title: String(values.title),
          description: String(values.description ?? ""),
          target_level: Number(values.target_level),
        });
      } else if (dialog === "action" && selectedGoal !== null) {
        const payload: Parameters<typeof createDevAction>[0] = {
          goal: selectedGoal,
          type: String(values.type),
          title: String(values.title),
        };
        if (values.due_date) payload.due_date = String(values.due_date);
        await createDevAction(payload);
      }
      setDialog(null);
      setNotice("Изменения ИПР сохранены");
      await load();
    } catch (caught) {
      setError(toApiError(caught).detail);
    } finally {
      setSubmitting(false);
    }
  }

  async function changeProgress(actionId: number, progress: number): Promise<void> {
    setError(null);
    try {
      await updateDevAction(actionId, { progress_percent: progress });
      setNotice("Прогресс сохранён");
      await load();
    } catch (caught) {
      setError(toApiError(caught).detail);
    }
  }

  async function advancePlan(plan: DevelopmentPlan): Promise<void> {
    const status = NEXT_PLAN_STATUS[plan.status];
    if (!status) return;
    try {
      await updateDevelopmentPlan(plan.id, { status });
      setNotice("Статус плана обновлён");
      await load();
    } catch (caught) {
      setError(toApiError(caught).detail);
    }
  }

  async function removeGoal(goalId: number): Promise<void> {
    try {
      await deleteDevGoal(goalId);
      await load();
    } catch (caught) {
      setError(toApiError(caught).detail);
    }
  }

  async function removeAction(actionId: number): Promise<void> {
    try {
      await deleteDevAction(actionId);
      await load();
    } catch (caught) {
      setError(toApiError(caught).detail);
    }
  }

  return (
    <div style={{ maxWidth: 960 }}>
      <Title level={1}>Индивидуальный план развития</Title>
      <Text type="secondary">Цели, действия и прогресс развития.</Text>

      {canEdit ? (
        <Space wrap style={{ marginTop: 16, display: "flex" }}>
          <Button type="primary" onClick={() => openDialog("manual-plan")}>
            Создать ИПР
          </Button>
          <Button onClick={() => openDialog("auto-plan")}>Автоподбор</Button>
        </Space>
      ) : null}
      {error ? <Alert type="error" message={error} showIcon style={{ marginTop: 16 }} /> : null}
      {notice ? <Alert type="success" message={notice} showIcon style={{ marginTop: 16 }} /> : null}

      <Spin spinning={loading}>
        {plans.length === 0 && !loading ? (
          <Empty description="План развития ещё не сформирован" style={{ marginTop: 24 }} />
        ) : (
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            {plans.map((plan) => (
              <Col span={24} key={plan.id}>
                <PlanCard
                  plan={plan}
                  canEdit={
                    canEdit &&
                    (options?.employees.some((employee) => employee.id === plan.employee) ?? false)
                  }
                  onProgress={(actionId, value) => void changeProgress(actionId, value)}
                  onAdvance={() => void advancePlan(plan)}
                  onAddGoal={() => openDialog("goal", plan.id)}
                  onAddAction={(goalId) => openDialog("action", plan.id, goalId)}
                  onDeleteGoal={(goalId) => void removeGoal(goalId)}
                  onDeleteAction={(actionId) => void removeAction(actionId)}
                />
              </Col>
            ))}
          </Row>
        )}
      </Spin>

      <Modal
        open={dialog !== null}
        title={dialogTitle(dialog)}
        okText={dialog === "auto-plan" ? "Сформировать" : "Создать"}
        cancelText="Отмена"
        confirmLoading={submitting}
        onCancel={() => setDialog(null)}
        onOk={() => form.submit()}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={(values) => void submit(values)}>
          {dialog === "manual-plan" || dialog === "auto-plan" ? (
            <Form.Item name="employee" label="Сотрудник" rules={[{ required: true }]}>
              <Select options={options?.employees.map(toSelectOption) ?? []} />
            </Form.Item>
          ) : null}
          {dialog === "manual-plan" ? (
            <Form.Item name="title" label="Название" rules={[{ required: true }]}>
              <Input maxLength={300} />
            </Form.Item>
          ) : null}
          {dialog === "auto-plan" ? (
            <Form.Item name="cycle" label="Цикл оценки" rules={[{ required: true }]}>
              <Select options={options?.cycles.map(toSelectOption) ?? []} />
            </Form.Item>
          ) : null}
          {dialog === "goal" ? <GoalFields options={options} /> : null}
          {dialog === "action" ? <ActionFields /> : null}
        </Form>
      </Modal>
    </div>
  );
}

interface PlanCardProps {
  plan: DevelopmentPlan;
  canEdit: boolean;
  onProgress: (actionId: number, progress: number) => void;
  onAdvance: () => void;
  onAddGoal: () => void;
  onAddAction: (goalId: number) => void;
  onDeleteGoal: (goalId: number) => void;
  onDeleteAction: (actionId: number) => void;
}

function PlanCard(props: PlanCardProps): React.JSX.Element {
  const { plan, canEdit } = props;
  return (
    <Card
      title={
        <Space wrap>
          <span>{plan.title}</span>
          <StatusBadge
            status={plan.status}
            label={PLAN_STATUS_LABELS[plan.status] ?? plan.status}
          />
        </Space>
      }
      extra={
        canEdit ? (
          <Space wrap>
            {NEXT_PLAN_STATUS[plan.status] ? (
              <Button size="small" onClick={props.onAdvance}>
                Следующий статус
              </Button>
            ) : null}
            <Button size="small" onClick={props.onAddGoal}>
              Добавить цель
            </Button>
          </Space>
        ) : null
      }
    >
      <Text type="secondary">{plan.employee_name}</Text>
      <Progress percent={plan.progress_percent} aria-label={`Прогресс плана ${plan.title}`} />
      <Text>{plan.progress_percent}% выполнено</Text>
      {plan.goals.length === 0 ? (
        <Empty description="Нет целей" />
      ) : (
        plan.goals.map((goal) => <GoalBlock key={goal.id} goal={goal} {...props} />)
      )}
    </Card>
  );
}

function GoalBlock({ goal, canEdit, ...props }: { goal: DevGoal } & PlanCardProps) {
  return (
    <section style={{ marginTop: 20 }}>
      <Space wrap>
        <Title level={5} style={{ margin: 0 }}>
          {goal.title}
        </Title>
        {canEdit ? (
          <>
            <Button size="small" onClick={() => props.onAddAction(goal.id)}>
              Добавить действие
            </Button>
            <Button size="small" danger onClick={() => props.onDeleteGoal(goal.id)}>
              Удалить цель
            </Button>
          </>
        ) : null}
      </Space>
      {goal.source.type === "assessment" ? (
        <Text type="secondary" style={{ display: "block", marginTop: 4 }}>
          {goal.source.cycle_name}: {goal.source.current_level} → {goal.source.expected_level}
        </Text>
      ) : (
        <Text type="secondary">Добавлено вручную</Text>
      )}
      {goal.actions.map((item) => (
        <div
          key={item.id}
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            padding: "10px 0",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <span>
            <Tag>{ACTION_TYPE_LABELS[item.type] ?? item.type}</Tag>
            {item.title}
          </span>
          <Space wrap>
            <StatusBadge
              status={item.status}
              label={ACTION_STATUS_LABELS[item.status] ?? item.status}
            />
            {canEdit ? (
              <>
                <Select
                  aria-label={`Прогресс: ${item.title}`}
                  value={item.progress_percent}
                  options={PROGRESS_OPTIONS}
                  style={{ width: 90 }}
                  onChange={(value) => props.onProgress(item.id, value)}
                />
                <Button size="small" danger onClick={() => props.onDeleteAction(item.id)}>
                  Удалить
                </Button>
              </>
            ) : (
              <Text>{item.progress_percent}%</Text>
            )}
          </Space>
        </div>
      ))}
    </section>
  );
}

function GoalFields({ options }: { options: IdpOptions | null }): React.JSX.Element {
  return (
    <>
      <Form.Item name="competency" label="Компетенция" rules={[{ required: true }]}>
        <Select options={options?.competencies.map(toSelectOption) ?? []} />
      </Form.Item>
      <Form.Item name="title" label="Цель" rules={[{ required: true }]}>
        <Input maxLength={300} />
      </Form.Item>
      <Form.Item name="description" label="Описание">
        <Input.TextArea maxLength={2000} />
      </Form.Item>
      <Form.Item
        name="target_level"
        label="Целевой уровень"
        initialValue={4}
        rules={[{ required: true }]}
      >
        <InputNumber min={1} max={10} />
      </Form.Item>
    </>
  );
}

function ActionFields(): React.JSX.Element {
  return (
    <>
      <Form.Item name="type" label="Тип действия" rules={[{ required: true }]}>
        <Select
          options={Object.entries(ACTION_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
        />
      </Form.Item>
      <Form.Item name="title" label="Действие" rules={[{ required: true }]}>
        <Input maxLength={300} />
      </Form.Item>
      <Form.Item name="due_date" label="Срок">
        <Input type="date" />
      </Form.Item>
    </>
  );
}

function dialogTitle(dialog: Dialog): string {
  if (dialog === "manual-plan") return "Новый ИПР";
  if (dialog === "auto-plan") return "Автоподбор из оценки";
  if (dialog === "goal") return "Новая цель";
  return "Новое действие";
}

function toSelectOption(item: { id: number; name: string }): { value: number; label: string } {
  return { value: item.id, label: item.name };
}
