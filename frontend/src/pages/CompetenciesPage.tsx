/**
 * Страница «Компетенции» (SPEC §4) — список компетенций по группам.
 *
 * Чтение доступно всем аутентифицированным. Создание/правка — HR/Методолог
 * (на UI появится в следующем инкременте с правами).
 */
import { Alert, Card, Col, Empty, Row, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";

import {
  getCompetencies,
  getCompetencyGroups,
  type Competency,
  type CompetencyGroup,
} from "@/api/competencies";
import { toApiError } from "@/api/client";

const { Title, Text } = Typography;

export function CompetenciesPage(): React.JSX.Element {
  const [groups, setGroups] = useState<CompetencyGroup[]>([]);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getCompetencyGroups(), getCompetencies()])
      .then(([g, c]) => {
        if (!cancelled) {
          setGroups(g);
          setCompetencies(c);
        }
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
    <div style={{ maxWidth: 960 }}>
      <Title level={1}>Компетенции</Title>
      <Text type="secondary">Модель компетенций и шаблоны организации.</Text>

      {error ? <Alert type="error" message={error} showIcon style={{ margin: "16px 0" }} /> : null}

      <Spin spinning={loading}>
        {groups.length === 0 && !loading ? (
          <Empty description="Нет данных" />
        ) : (
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            {groups.map((group) => (
              <Col xs={24} md={12} key={group.id}>
                <Card title={group.name} variant="outlined">
                  {competencies
                    .filter((c) => c.group === group.id)
                    .map((c) => (
                      <Tag key={c.id} style={{ marginBottom: 8 }}>
                        {c.name}
                      </Tag>
                    ))}
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </div>
  );
}
