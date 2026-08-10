/**
 * Дашборд сотрудника (SPEC §9.2, issue #15).
 *
 * Показывает радар компетенций (агрегаты) и динамику по циклам.
 * Данные — из GET /analytics/employees/<id>/dashboard/ (только агрегаты,
 * без сырых оценок, SPEC §6.3).
 * Employee ID берётся только из безопасного контекста текущей сессии `/auth/me/`.
 */
import { Alert, Card, Col, Empty, Row, Spin, Typography } from "antd";
import { useEffect, useState } from "react";

import { CompetencyRadar } from "@/components/CompetencyRadar";
import { getEmployeeDashboard, type EmployeeDashboard } from "@/api/analytics";
import { toApiError } from "@/api/client";
import { useAuth } from "@/app/auth-context";

const { Title, Text } = Typography;

export function DashboardPage(): React.JSX.Element {
  const { user } = useAuth();
  const employeeId = user?.employeeId ?? null;
  const [dashboard, setDashboard] = useState<EmployeeDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (employeeId === null) {
      setDashboard(null);
      setLoading(false);
      return;
    }
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
          setError(
            err.status === 403 ? "У вас нет доступа к дашборду этого сотрудника." : err.detail,
          );
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

      {employeeId === null ? (
        <Alert
          type="warning"
          message="Профиль сотрудника не привязан к вашей учётной записи."
          showIcon
          style={{ marginTop: 16 }}
        />
      ) : null}

      {error ? <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} /> : null}

      <Spin spinning={loading}>
        {dashboard ? (
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card title="Профиль компетенций" variant="outlined">
                <CompetencyRadar profile={dashboard.competency_profile} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title={dashboard.employee.full_name || "Сотрудник"} variant="outlined">
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
