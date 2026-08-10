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
  Row,
  Select,
  Space,
  Spin,
  Steps,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";

import {
  CYCLE_STATUS_LABELS,
  GROUP_LABELS,
  createCycle,
  getCycleResults,
  getCycles,
  getSetupOptions,
  startCycle,
  type AssessmentCycle,
  type CreateCyclePayload,
  type CycleResults,
  type SetupOptions,
} from "@/api/assessment";
import { toApiError } from "@/api/client";
import { StatusBadge } from "@/components/StatusBadge";

const { Text, Title } = Typography;

export function CycleManager({ canManage }: { canManage: boolean }): React.JSX.Element {
  const [cycles, setCycles] = useState<AssessmentCycle[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [resultsCycle, setResultsCycle] = useState<AssessmentCycle | null>(null);
  const [results, setResults] = useState<CycleResults | null>(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [setupOptions, setSetupOptions] = useState<SetupOptions | null>(null);
  const [setupLoading, setSetupLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<CreateCyclePayload>();

  const loadCycles = () => {
    setLoading(true);
    setError(null);
    getCycles()
      .then(setCycles)
      .catch((reason) => setError(toApiError(reason).detail))
      .finally(() => setLoading(false));
  };

  useEffect(loadCycles, []);

  const openWizard = () => {
    setWizardOpen(true);
    setSetupLoading(true);
    setError(null);
    getSetupOptions()
      .then(setSetupOptions)
      .catch((reason) => setError(toApiError(reason).detail))
      .finally(() => setSetupLoading(false));
  };

  const submitWizard = async (payload: CreateCyclePayload) => {
    setCreating(true);
    setError(null);
    try {
      const cycle = await createCycle(payload);
      setCycles((items) => [cycle, ...items]);
      setWizardOpen(false);
      setSuccess("Цикл создан, оценщики назначены.");
      form.resetFields();
    } catch (reason) {
      setError(toApiError(reason).detail);
    } finally {
      setCreating(false);
    }
  };

  const runCycle = async (cycle: AssessmentCycle) => {
    setError(null);
    try {
      const updated = await startCycle(cycle.id);
      setCycles((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      setSuccess("Цикл запущен. Участники могут заполнять оценки.");
    } catch (reason) {
      setError(toApiError(reason).detail);
    }
  };

  const showResults = (cycle: AssessmentCycle) => {
    setResultsCycle(cycle);
    setResults(null);
    setResultsError(null);
    setResultsLoading(true);
    getCycleResults(cycle.id)
      .then(setResults)
      .catch((reason) => setResultsError(toApiError(reason).detail))
      .finally(() => setResultsLoading(false));
  };

  const columns: ColumnsType<AssessmentCycle> = [
    { title: "Цикл", dataIndex: "name", key: "name" },
    {
      title: "Статус",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <StatusBadge status={status} label={CYCLE_STATUS_LABELS[status] ?? status} />
      ),
    },
    { title: "Дедлайн", dataIndex: "deadline", key: "deadline", render: (date) => date ?? "—" },
    {
      title: "Порог",
      dataIndex: "anonymity_threshold",
      key: "anonymity_threshold",
      render: (value: number) => `≥ ${value}`,
    },
    {
      title: "",
      key: "actions",
      render: (_: unknown, cycle: AssessmentCycle) => (
        <Space>
          {canManage && cycle.status === "assigned" ? (
            <Button type="link" onClick={() => void runCycle(cycle)}>
              Запустить
            </Button>
          ) : null}
          {cycle.status === "aggregated" || cycle.status === "closed" ? (
            <Button type="link" onClick={() => showResults(cycle)}>
              Результаты
            </Button>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <section aria-labelledby="cycles-title" style={{ marginTop: 32 }}>
      <Space style={{ display: "flex", justifyContent: "space-between" }}>
        <Title level={2} id="cycles-title" style={{ margin: 0 }}>
          Циклы оценки
        </Title>
        {canManage ? (
          <Button type="primary" onClick={openWizard}>
            Создать цикл
          </Button>
        ) : null}
      </Space>
      {success ? (
        <Alert type="success" message={success} showIcon closable style={{ marginTop: 16 }} />
      ) : null}
      {error ? <Alert type="error" message={error} showIcon style={{ marginTop: 16 }} /> : null}
      <Spin spinning={loading}>
        {cycles.length === 0 && !loading ? (
          <Empty description="Пока нет циклов оценки" style={{ marginTop: 24 }} />
        ) : (
          <Table<AssessmentCycle>
            columns={columns}
            dataSource={cycles}
            rowKey="id"
            style={{ marginTop: 16 }}
            pagination={{ pageSize: 10 }}
          />
        )}
      </Spin>

      <Modal
        title="Мастер создания цикла"
        open={wizardOpen}
        onCancel={() => setWizardOpen(false)}
        onOk={() => form.submit()}
        okText="Создать"
        confirmLoading={creating}
        width={680}
      >
        <Spin spinning={setupLoading}>
          <Steps
            current={2}
            size="small"
            items={[{ title: "Шаблон" }, { title: "Команда" }, { title: "Сроки" }]}
            style={{ marginBottom: 24 }}
          />
          <Form<CreateCyclePayload>
            form={form}
            layout="vertical"
            initialValues={{ anonymity_threshold: 3 }}
            onFinish={(values) => void submitWizard(values)}
          >
            <Form.Item name="name" label="Название цикла" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="framework" label="Модель компетенций" rules={[{ required: true }]}>
              <Select
                options={(setupOptions?.frameworks ?? []).map((item) => ({
                  value: item.id,
                  label: item.name,
                }))}
              />
            </Form.Item>
            <Form.Item name="participant_ids" label="Участники" rules={[{ required: true }]}>
              <Select
                mode="multiple"
                optionFilterProp="label"
                options={(setupOptions?.participants ?? []).map((item) => ({
                  value: item.id,
                  label: `${item.full_name} · ${item.department}`,
                }))}
              />
            </Form.Item>
            <Row gutter={16}>
              <Col xs={24} sm={12}>
                <Form.Item name="start_date" label="Дата начала" rules={[{ required: true }]}>
                  <Input type="date" />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12}>
                <Form.Item name="deadline" label="Дедлайн" rules={[{ required: true }]}>
                  <Input type="date" />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item
              name="anonymity_threshold"
              label="Порог анонимности"
              rules={[{ required: true }]}
            >
              <InputNumber min={2} max={20} />
            </Form.Item>
          </Form>
        </Spin>
      </Modal>

      <Modal
        title={resultsCycle ? `Результаты: ${resultsCycle.name}` : "Результаты"}
        open={resultsCycle !== null}
        onCancel={() => setResultsCycle(null)}
        footer={null}
        width={620}
      >
        <Spin spinning={resultsLoading}>
          {resultsError ? <Alert type="error" message={resultsError} showIcon /> : null}
          {results ? <ResultsView results={results} /> : null}
        </Spin>
      </Modal>
    </section>
  );
}

function ResultsView({ results }: { results: CycleResults }): React.JSX.Element {
  return (
    <div>
      <Text type="secondary">Средние оценки по группам оценщиков. Сырые ответы скрыты.</Text>
      <Row gutter={[8, 8]} style={{ marginTop: 16 }}>
        {results.groups.map((group) => (
          <Col span={12} key={group.group}>
            <Card size="small">
              <Text strong>{GROUP_LABELS[group.group] ?? group.group}</Text>
              <div style={{ marginTop: 8 }}>
                {group.hidden_by_threshold ? (
                  <Tag>Скрыто: оценщиков меньше порога</Tag>
                ) : (
                  <>
                    <Text>Средний балл: </Text>
                    <Text strong>{group.mean_score}</Text>
                    <Text type="secondary"> (оценщиков: {group.participants_count})</Text>
                  </>
                )}
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
