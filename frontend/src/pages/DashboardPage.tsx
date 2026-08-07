/**
 * Дашборд сотрудника (SPEC §9.2, issue #15).
 *
 * Показывает радар компетенций (агрегаты) и динамику по циклам.
 * Данные — из GET /analytics/employees/<id>/dashboard/ (только агрегаты,
 * без сырых оценок, SPEC §6.3).
 *
 * TODO: после добавления /auth/me — employeeId текущего сотрудника автоматически.
 * Сейчас — выбор ID для демонстрации RBAC (403 на чужого).
 */
import { Alert, Card, Col, Empty, InputNumber, Row, Spin, Typography } from "antd";
import { useEffect, useState } from "react";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { getEmployeeDashboard, type EmployeeDashboard } from "@/api/analytics";
import { toApiError } from "@/api/client";

const { Title, Text } = Typography;

export function DashboardPage(): React.JSX.Element {
  const [employeeId, setEmployeeId] = useState(1);
  const [dashboard, setDashboard] = useState<EmployeeDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getEmployeeDashboard(employeeId)
      .then((data) => {
        if (!cancelled) setDashboard(data);
      })
      .catch((e) => {
        if (!cancelled) {
          const err = toApiError(e);
          setError(err.detail);
          setDashboard(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [employeeId]);

  return (
    <div style={{ maxWidth: 960 }}>
      <Title level={1}>Дашборд сотрудника</Title>
      <Text type="secondary">Профиль компетенций и динамика по циклам оценки.</Text>

      <div style={{ margin: "16px 0" }}>
        <Text type="secondary">ID сотрудника: </Text>
        <InputNumber
          min={1}
          value={employeeId}
          onChange={(v) => setEmployeeId(Number(v) || 1)}
          size="small"
        />
      </div>

      {error ? <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} /> : null}

      <Spin spinning={loading}>
        {dashboard ? (
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card title="Профиль компетенций" bordered>
                <CompetencyRadar profile={dashboard.competency_profile} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title={dashboard.employee.full_name || "Сотрудник"} bordered>
                <p>
                  <Text type="secondary">Подразделение: </Text>
                  <Text>{dashboard.employee.department || "—"}</Text>
                </p>
                <p>
                  <Text type="secondary">Должность: </Text>
                  <Text>{dashboard.employee.position || "—"}</Text>
                </p>
                <Title level={5} style={{ marginTop: 16 }}>
                  Динамика по циклам
                </Title>
                {dashboard.cycle_dynamics.length === 0 ? (
                  <Empty description="Нет завершённых циклов" />
                ) : (
                  <ul style={{ paddingLeft: 16 }}>
                    {dashboard.cycle_dynamics.map((d) => (
                      <li key={d.cycle_id}>
                        {d.cycle_name}: <strong>{d.overall_mean}</strong>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </Col>
          </Row>
        ) : null}
      </Spin>
    </div>
  );
}
