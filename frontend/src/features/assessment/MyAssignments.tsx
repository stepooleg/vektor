import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Radio,
  Spin,
  Tag,
  Typography,
} from "antd";
import { useEffect, useState } from "react";

import {
  GROUP_LABELS,
  getMyAssignments,
  submitAssignment,
  type AssignmentSubmitPayload,
  type ReviewerAssignment,
} from "@/api/assessment";
import { toApiError } from "@/api/client";

const { Paragraph, Text, Title } = Typography;

export function MyAssignments(): React.JSX.Element {
  const [assignments, setAssignments] = useState<ReviewerAssignment[]>([]);
  const [selected, setSelected] = useState<ReviewerAssignment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMyAssignments()
      .then((data) => {
        if (!cancelled) setAssignments(data);
      })
      .catch((reason) => {
        if (!cancelled) setError(toApiError(reason).detail);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const markCompleted = (assignmentId: number) => {
    setAssignments((items) =>
      items.map((item) => (item.id === assignmentId ? { ...item, completed: true } : item)),
    );
    setSelected(null);
    setSuccess("Оценка отправлена");
  };

  return (
    <section aria-labelledby="my-assessments-title" style={{ marginTop: 24 }}>
      <Title level={2} id="my-assessments-title">
        Мои оценки
      </Title>
      {success ? <Alert type="success" message={success} showIcon closable /> : null}
      {error ? <Alert type="error" message={error} showIcon /> : null}
      <Spin spinning={loading}>
        {assignments.length === 0 && !loading ? (
          <Empty description="Нет назначенных оценок" />
        ) : (
          <List
            grid={{ gutter: 16, xs: 1, md: 2 }}
            dataSource={assignments}
            renderItem={(assignment) => (
              <List.Item>
                <Card
                  title={assignment.cycle_name}
                  extra={
                    <Tag color={assignment.completed ? "success" : "processing"}>
                      {assignment.completed ? "Заполнено" : "Ожидает заполнения"}
                    </Tag>
                  }
                >
                  <Paragraph>
                    Оцениваемый: <Text strong>{assignment.participant_name}</Text>
                  </Paragraph>
                  <Paragraph type="secondary">
                    Роль: {GROUP_LABELS[assignment.group] ?? assignment.group}
                    {assignment.deadline ? ` · до ${assignment.deadline}` : ""}
                  </Paragraph>
                  {!assignment.completed ? (
                    <Button type="primary" onClick={() => setSelected(assignment)}>
                      Пройти оценку
                    </Button>
                  ) : null}
                </Card>
              </List.Item>
            )}
          />
        )}
      </Spin>
      <QuestionnaireModal
        assignment={selected}
        onClose={() => setSelected(null)}
        onCompleted={markCompleted}
      />
    </section>
  );
}

function QuestionnaireModal({
  assignment,
  onClose,
  onCompleted,
}: {
  assignment: ReviewerAssignment | null;
  onClose: () => void;
  onCompleted: (assignmentId: number) => void;
}): React.JSX.Element {
  const [scores, setScores] = useState<Record<number, number>>({});
  const [comments, setComments] = useState<Record<number, string>>({});
  const [generalComment, setGeneralComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (assignment === null) return;
    if (assignment.competencies.some((item) => scores[item.id] === undefined)) {
      setError("Поставьте оценку по каждой компетенции.");
      return;
    }
    const payload: AssignmentSubmitPayload = {
      responses: assignment.competencies.map((item) => ({
        competency_id: item.id,
        score: scores[item.id],
        comment: comments[item.id] ?? "",
      })),
      general_comment: generalComment,
    };
    setSubmitting(true);
    setError(null);
    try {
      await submitAssignment(assignment.id, payload);
      setScores({});
      setComments({});
      setGeneralComment("");
      onCompleted(assignment.id);
    } catch (reason) {
      setError(toApiError(reason).detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={assignment ? `Оценка: ${assignment.participant_name}` : "Оценка"}
      open={assignment !== null}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Отмена
        </Button>,
        <Button key="submit" type="primary" loading={submitting} onClick={() => void submit()}>
          Отправить оценку
        </Button>,
      ]}
      width={720}
      destroyOnHidden
    >
      {error ? <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} /> : null}
      {assignment?.competencies.map((competency) => (
        <Card key={competency.id} size="small" style={{ marginBottom: 16 }}>
          <Title level={4}>{competency.name}</Title>
          {competency.description ? (
            <Paragraph type="secondary">{competency.description}</Paragraph>
          ) : null}
          <Radio.Group
            aria-label={`Оценка: ${competency.name}`}
            value={scores[competency.id]}
            onChange={(event) =>
              setScores((current) => ({ ...current, [competency.id]: Number(event.target.value) }))
            }
          >
            {Array.from(
              { length: competency.max_value - competency.min_value + 1 },
              (_, index) => competency.min_value + index,
            ).map((value) => (
              <Radio key={value} value={value}>
                {value}
              </Radio>
            ))}
          </Radio.Group>
          <Input.TextArea
            aria-label={`Комментарий: ${competency.name}`}
            placeholder="Комментарий (необязательно)"
            value={comments[competency.id] ?? ""}
            onChange={(event) =>
              setComments((current) => ({ ...current, [competency.id]: event.target.value }))
            }
            style={{ marginTop: 12 }}
          />
        </Card>
      ))}
      <Form.Item label="Общий комментарий" htmlFor="assessment-general-comment">
        <Input.TextArea
          id="assessment-general-comment"
          value={generalComment}
          onChange={(event) => setGeneralComment(event.target.value)}
        />
      </Form.Item>
    </Modal>
  );
}
