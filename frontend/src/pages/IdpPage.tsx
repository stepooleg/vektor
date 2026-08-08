/**
 * Модуль ИПР — просмотр плана развития (SPEC §14.4, §8.2, issue #26).
 *
 * Показывает цели и действия с бейджами статусов (BRANDBOOK §6.8).
 */
import { Alert, Card, Col, Empty, Row, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import {
  ACTION_STATUS_LABELS,
  ACTION_TYPE_LABELS,
  PLAN_STATUS_LABELS,
  type DevelopmentPlan,
  getDevelopmentPlans,
} from "@/api/idp";
import { toApiError } from "@/api/client";

const { Title, Text } = Typography;

export function IdpPage(): React.JSX.Element {
  const [plans, setPlans] = useState<DevelopmentPlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDevelopmentPlans()
      .then((data) => {
        if (!cancelled) setPlans(data);
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
      <Title level={1}>Индивидуальный план развития</Title>
      <Text type="secondary">Цели, действия и прогресс развития.</Text>

      {error ? <Alert type="error" message={error} showIcon style={{ margin: "16px 0" }} /> : null}

      <Spin spinning={loading}>
        {plans.length === 0 && !loading ? (
          <Empty description="План развития ещё не сформирован" style={{ marginTop: 24 }} />
        ) : (
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            {plans.map((plan) => (
              <Col span={24} key={plan.id}>
                <Card
                  title={
                    <span>
                      {plan.title}{" "}
                      <StatusBadge
                        status={plan.status}
                        label={PLAN_STATUS_LABELS[plan.status] ?? plan.status}
                      />
                    </span>
                  }
                  bordered
                >
                  {plan.goals.length === 0 ? (
                    <Empty description="Нет целей" />
                  ) : (
                    plan.goals.map((goal) => (
                      <div key={goal.id} style={{ marginBottom: 16 }}>
                        <Title level={5}>{goal.title}</Title>
                        {goal.actions.map((action) => (
                          <div
                            key={action.id}
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              padding: "8px 0",
                              borderBottom: "1px solid var(--border)",
                            }}
                          >
                            <span>
                              <Tag>{ACTION_TYPE_LABELS[action.type] ?? action.type}</Tag>
                              {action.title}
                            </span>
                            <StatusBadge
                              status={action.status}
                              label={ACTION_STATUS_LABELS[action.status] ?? action.status}
                            />
                          </div>
                        ))}
                      </div>
                    ))
                  )}
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </div>
  );
}
