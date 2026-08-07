/**
 * Модуль оценки (SPEC §14.2, issue #17).
 *
 * Список циклов с бейджами статусов (BRANDBOOK §6.8) и просмотр результатов:
 * только агрегаты по группам оценщиков, группы ниже порога скрыты (SPEC §6.3).
 */
import { Alert, Button, Card, Col, Empty, Modal, Row, Spin, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import {
  CYCLE_STATUS_LABELS,
  GROUP_LABELS,
  getCycleResults,
  getCycles,
  type AssessmentCycle,
  type CycleResults,
} from "@/api/assessment";
import { toApiError } from "@/api/client";

const { Title, Text } = Typography;

export function AssessmentPage(): React.JSX.Element {
  const [cycles, setCycles] = useState<AssessmentCycle[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultsCycle, setResultsCycle] = useState<AssessmentCycle | null>(null);
  const [results, setResults] = useState<CycleResults | null>(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCycles()
      .then((data) => {
        if (!cancelled) setCycles(data);
      })
      .catch((e) => {
        if (!cancelled) setError(toApiError(e).detail);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const showResults = (cycle: AssessmentCycle) => {
    setResultsCycle(cycle);
    setResults(null);
    setResultsError(null);
    setResultsLoading(true);
    getCycleResults(cycle.id)
      .then(setResults)
      .catch((e) => setResultsError(toApiError(e).detail))
      .finally(() => setResultsLoading(false));
  };

  const columns: ColumnsType<AssessmentCycle> = [
    {
      title: "Цикл",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "Статус",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <StatusBadge status={status} label={CYCLE_STATUS_LABELS[status] ?? status} />
      ),
    },
    {
      title: "Дедлайн",
      dataIndex: "deadline",
      key: "deadline",
      render: (d: string | null) => d ?? "—",
    },
    {
      title: "Порог",
      dataIndex: "anonymity_threshold",
      key: "anonymity_threshold",
      render: (v: number) => `≥ ${v}`,
    },
    {
      title: "",
      key: "actions",
      render: (_: unknown, record: AssessmentCycle) =>
        record.status === "aggregated" || record.status === "closed" ? (
          <Button type="link" onClick={() => showResults(record)}>
            Результаты
          </Button>
        ) : null,
    },
  ];

  return (
    <div style={{ maxWidth: 1000 }}>
      <Title level={1}>Оценка 360°</Title>
      <Text type="secondary">Циклы оценки и агрегированные результаты.</Text>

      {error ? <Alert type="error" message={error} showIcon style={{ margin: "16px 0" }} /> : null}

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
        title={resultsCycle ? `Результаты: ${resultsCycle.name}` : "Результаты"}
        open={!!resultsCycle}
        onCancel={() => setResultsCycle(null)}
        footer={null}
        width={620}
      >
        <Spin spinning={resultsLoading}>
          {resultsError ? <Alert type="error" message={resultsError} showIcon /> : null}
          {results ? <ResultsView results={results} /> : null}
        </Spin>
      </Modal>
    </div>
  );
}

/** Просмотр агрегированных результатов по группам (SPEC §6.3). */
function ResultsView({ results }: { results: CycleResults }): React.JSX.Element {
  return (
    <div>
      <Text type="secondary">Средние оценки по группам оценщиков. Сырые ответы скрыты.</Text>
      <Row gutter={[8, 8]} style={{ marginTop: 16 }}>
        {results.groups.map((g) => {
          const label = GROUP_LABELS[g.group] ?? g.group;
          if (g.hidden_by_threshold) {
            return (
              <Col span={12} key={g.group}>
                <Card size="small">
                  <Text strong>{label}</Text>
                  <div style={{ marginTop: 8 }}>
                    <Tag>Скрыто: оценщиков меньше порога</Tag>
                  </div>
                </Card>
              </Col>
            );
          }
          return (
            <Col span={12} key={g.group}>
              <Card size="small">
                <Text strong>{label}</Text>
                <div style={{ marginTop: 8 }}>
                  <Text>Средний балл: </Text>
                  <Text strong>{g.mean_score}</Text>
                  <Text type="secondary"> (оценщиков: {g.participants_count})</Text>
                </div>
              </Card>
            </Col>
          );
        })}
      </Row>
    </div>
  );
}
