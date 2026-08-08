/**
 * Страница аналитики — дашборд компании (SPEC §9.1, §14.5, issue #35).
 *
 * Метрики: охват оценок, средний балл, KPI. Агрегаты без сырых данных.
 */
import { Alert, Card, Col, Empty, Row, Spin, Statistic, Typography } from "antd";
import { useEffect, useState } from "react";

import { type CompanyDashboard, getCompanyDashboard } from "@/api/analytics-dashboard";
import { toApiError } from "@/api/client";

const { Title, Text } = Typography;

export function AnalyticsPage(): React.JSX.Element {
  const [dashboard, setDashboard] = useState<CompanyDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCompanyDashboard()
      .then((data) => {
        if (!cancelled) setDashboard(data);
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

  return (
    <div style={{ maxWidth: 900 }}>
      <Title level={1}>Аналитика</Title>
      <Text type="secondary">Сводные метрики по компании.</Text>

      {error ? (
        error.includes("403") ? (
          <Alert
            type="info"
            message="Дашборд компании доступен HR и руководителям."
            style={{ margin: "16px 0" }}
          />
        ) : (
          <Alert type="error" message={error} showIcon style={{ margin: "16px 0" }} />
        )
      ) : null}

      <Spin spinning={loading}>
        {dashboard ? (
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={12} md={8}>
              <Card>
                <Statistic title="Всего сотрудников" value={dashboard.total_employees} />
              </Card>
            </Col>
            <Col xs={12} md={8}>
              <Card>
                <Statistic title="С завершённой оценкой" value={dashboard.assessed_employees} />
              </Card>
            </Col>
            <Col xs={12} md={8}>
              <Card>
                <Statistic title="Охват оценки" value={dashboard.assessment_coverage} suffix="%" />
              </Card>
            </Col>
            <Col xs={12} md={8}>
              <Card>
                <Statistic title="Средний балл" value={dashboard.average_score} precision={2} />
              </Card>
            </Col>
            <Col xs={12} md={8}>
              <Card>
                <Statistic title="Всего циклов" value={dashboard.total_cycles} />
              </Card>
            </Col>
          </Row>
        ) : !loading && !error ? (
          <Empty description="Нет данных" />
        ) : null}
      </Spin>
    </div>
  );
}
