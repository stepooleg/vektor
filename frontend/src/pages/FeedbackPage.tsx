/** Непрерывная обратная связь: благодарности и запросы (SPEC §6.1, issue #69). */
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
} from "antd";
import { useEffect, useState } from "react";

import {
  createFeedbackRequest,
  createPraise,
  FEEDBACK_REQUEST_STATUS_LABELS,
  type FeedbackRecipient,
  type FeedbackRequest,
  getFeedbackRecipients,
  getFeedbackRequests,
  getPraises,
  type Praise,
} from "@/api/feedback";
import { toApiError } from "@/api/client";

const { Paragraph, Text, Title } = Typography;
type Dialog = "praise" | "request" | null;

export function FeedbackPage(): React.JSX.Element {
  const [praises, setPraises] = useState<Praise[]>([]);
  const [requests, setRequests] = useState<FeedbackRequest[]>([]);
  const [recipients, setRecipients] = useState<FeedbackRecipient[]>([]);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    let cancelled = false;
    Promise.all([getPraises(), getFeedbackRequests(), getFeedbackRecipients()])
      .then(([praiseData, requestData, recipientData]) => {
        if (!cancelled) {
          setPraises(praiseData);
          setRequests(requestData);
          setRecipients(recipientData);
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

  function openDialog(next: Exclude<Dialog, null>): void {
    setDialog(next);
    setError(null);
    setNotice(null);
    form.resetFields();
  }

  async function submit(values: Record<string, unknown>): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      if (dialog === "praise") {
        const praise = await createPraise({
          recipient: Number(values.recipient),
          message: String(values.message),
          is_public: values.is_public !== false,
          is_anonymous: values.is_anonymous === true,
        });
        setPraises((current) => [praise, ...current]);
        setNotice("Благодарность отправлена");
      } else {
        const request = await createFeedbackRequest({
          recipient: Number(values.recipient),
          message: String(values.message ?? ""),
        });
        setRequests((current) => [request, ...current]);
        setNotice("Запрос отправлен");
      }
      setDialog(null);
    } catch (reason) {
      setError(toApiError(reason).detail);
    } finally {
      setSubmitting(false);
    }
  }

  const recipientOptions = recipients.map((recipient) => ({
    value: recipient.id,
    label: `${recipient.full_name} · ${recipient.department}`,
  }));

  return (
    <div style={{ maxWidth: 1000 }}>
      <Title level={1}>Обратная связь</Title>
      <Text type="secondary">Благодарите коллег и запрашивайте обратную связь в любой момент.</Text>
      <Space wrap style={{ margin: "16px 0" }}>
        <Button type="primary" onClick={() => openDialog("praise")}>
          Отправить благодарность
        </Button>
        <Button onClick={() => openDialog("request")}>Запросить обратную связь</Button>
      </Space>
      {notice ? (
        <Alert type="success" showIcon message={notice} style={{ marginBottom: 16 }} />
      ) : null}
      {error ? <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} /> : null}

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={14}>
            <Card title="Лента благодарностей">
              {praises.length === 0 ? (
                <Empty description="Пока нет благодарностей" />
              ) : (
                <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                  {praises.map((praise) => (
                    <div key={praise.id}>
                      <Text strong>{praise.sender_name ?? "Аноним"}</Text>
                      <Text type="secondary"> → {praise.recipient_name}</Text>
                      {!praise.is_public ? <Tag style={{ marginLeft: 8 }}>Приватно</Tag> : null}
                      <Paragraph style={{ margin: "4px 0 0" }}>{praise.message}</Paragraph>
                    </div>
                  ))}
                </Space>
              )}
            </Card>
          </Col>
          <Col xs={24} lg={10}>
            <Card title="Мои запросы">
              {requests.length === 0 ? (
                <Empty description="Нет активных запросов" />
              ) : (
                <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                  {requests.map((request) => (
                    <div key={request.id}>
                      <Text strong>{request.recipient_name}</Text>
                      <Tag style={{ marginLeft: 8 }}>
                        {FEEDBACK_REQUEST_STATUS_LABELS[request.status] ?? request.status}
                      </Tag>
                      {request.message ? <Paragraph>{request.message}</Paragraph> : null}
                    </div>
                  ))}
                </Space>
              )}
            </Card>
          </Col>
        </Row>
      </Spin>

      <Modal
        open={dialog !== null}
        title={dialog === "praise" ? "Новая благодарность" : "Запрос обратной связи"}
        footer={null}
        destroyOnHidden
        onCancel={() => setDialog(null)}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ is_public: true, is_anonymous: false }}
          onFinish={(values) => void submit(values as Record<string, unknown>)}
        >
          <Form.Item
            name="recipient"
            label={dialog === "praise" ? "Получатель" : "Коллега"}
            rules={[{ required: true, message: "Выберите сотрудника" }]}
          >
            <Select showSearch optionFilterProp="label" options={recipientOptions} />
          </Form.Item>
          <Form.Item
            name="message"
            label={dialog === "praise" ? "Текст благодарности" : "Контекст запроса"}
            rules={
              dialog === "praise" ? [{ required: true, message: "Напишите благодарность" }] : []
            }
          >
            <Input.TextArea rows={4} maxLength={2000} showCount />
          </Form.Item>
          {dialog === "praise" ? (
            <Space size="large" style={{ marginBottom: 20 }}>
              <Form.Item name="is_public" label="Публичная" valuePropName="checked" noStyle>
                <Switch />
              </Form.Item>
              <Form.Item name="is_anonymous" label="Анонимная" valuePropName="checked" noStyle>
                <Switch />
              </Form.Item>
            </Space>
          ) : null}
          <div>
            <Button type="primary" htmlType="submit" loading={submitting}>
              {dialog === "praise" ? "Отправить" : "Отправить запрос"}
            </Button>
          </div>
        </Form>
      </Modal>
    </div>
  );
}
