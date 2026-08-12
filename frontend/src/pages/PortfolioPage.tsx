/** Личный журнал достижений (SPEC §6.2, issue #69). */
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Timeline,
  Typography,
} from "antd";
import { useEffect, useState } from "react";

import {
  createPortfolioEntry,
  getPortfolioEntries,
  getPortfolioTargets,
  PORTFOLIO_TYPE_LABELS,
  type PortfolioEntry,
  type PortfolioTarget,
} from "@/api/feedback";
import { toApiError } from "@/api/client";

const { Paragraph, Text, Title } = Typography;

export function PortfolioPage(): React.JSX.Element {
  const [entries, setEntries] = useState<PortfolioEntry[]>([]);
  const [targets, setTargets] = useState<PortfolioTarget[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    let cancelled = false;
    Promise.all([getPortfolioEntries(), getPortfolioTargets()])
      .then(([entryData, targetData]) => {
        if (!cancelled) {
          setEntries(entryData);
          setTargets(targetData);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(toApiError(reason).detail);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function openDialog(): void {
    const self = targets.find((target) => target.is_self);
    form.setFieldsValue({ employee: self?.id, type: "achievement", title: "", description: "" });
    setNotice(null);
    setError(null);
    setDialogOpen(true);
  }

  async function submit(values: {
    employee?: number;
    type: "achievement" | "project";
    title: string;
    description?: string;
  }): Promise<void> {
    setSubmitting(true);
    try {
      const employeeId = values.employee ?? targets.find((target) => target.is_self)?.id;
      if (employeeId === undefined) {
        setError("Не удалось определить владельца портфолио.");
        return;
      }
      const entry = await createPortfolioEntry({
        employee: employeeId,
        type: values.type,
        title: values.title,
        description: values.description ?? "",
      });
      setEntries((current) => [entry, ...current]);
      setNotice("Достижение добавлено");
      setDialogOpen(false);
    } catch (reason) {
      setError(toApiError(reason).detail);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 900 }}>
      <Title level={1}>Портфолио</Title>
      <Text type="secondary">Достижения, проекты, благодарности и пройденные курсы.</Text>
      <div style={{ margin: "16px 0" }}>
        <Button type="primary" onClick={openDialog}>
          Добавить достижение
        </Button>
      </div>
      {notice ? (
        <Alert type="success" showIcon message={notice} style={{ marginBottom: 16 }} />
      ) : null}
      {error ? <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} /> : null}
      <Spin spinning={loading}>
        <Card title="Журнал достижений">
          {entries.length === 0 ? (
            <Empty description="Пока нет записей" />
          ) : (
            <Timeline
              items={entries.map((entry) => ({
                children: (
                  <Space direction="vertical" size={2}>
                    <div>
                      <Tag>{PORTFOLIO_TYPE_LABELS[entry.type] ?? entry.type}</Tag>
                      <Text strong>{entry.title}</Text>
                    </div>
                    {entry.employee_name ? (
                      <Text type="secondary">{entry.employee_name}</Text>
                    ) : null}
                    {entry.description ? <Paragraph>{entry.description}</Paragraph> : null}
                  </Space>
                ),
              }))}
            />
          )}
        </Card>
      </Spin>

      <Modal
        open={dialogOpen}
        title="Новое достижение"
        footer={null}
        destroyOnHidden
        onCancel={() => setDialogOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={(values) => void submit(values)}>
          {targets.length > 1 ? (
            <Form.Item name="employee" label="Сотрудник" rules={[{ required: true }]}>
              <Select
                options={targets.map((target) => ({
                  value: target.id,
                  label: `${target.full_name} · ${target.department}`,
                }))}
              />
            </Form.Item>
          ) : null}
          <Form.Item name="type" label="Тип" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "achievement", label: "Достижение" },
                { value: "project", label: "Проект/кейс" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="title"
            label="Название"
            rules={[{ required: true, message: "Укажите название" }]}
          >
            <Input maxLength={300} />
          </Form.Item>
          <Form.Item name="description" label="Описание">
            <Input.TextArea rows={4} maxLength={2000} showCount />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting}>
            Добавить
          </Button>
        </Form>
      </Modal>
    </div>
  );
}
