/**
 * Страница обратной связи и портфолио (SPEC §14.6, §6.1, §6.2, issue #34).
 *
 * Лента благодарностей + журнал достижений (портфолио).
 */
import { Alert, Card, Col, Empty, Row, Spin, Tag, Timeline, Typography } from "antd";
import { useEffect, useState } from "react";

import {
  PORTFOLIO_TYPE_LABELS,
  type PortfolioEntry,
  type Praise,
  getPortfolioEntries,
  getPraises,
} from "@/api/feedback";
import { toApiError } from "@/api/client";

const { Title, Text } = Typography;

export function FeedbackPage(): React.JSX.Element {
  const [praises, setPraises] = useState<Praise[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getPraises(), getPortfolioEntries()])
      .then(([p, pf]) => {
        if (!cancelled) {
          setPraises(p);
          setPortfolio(pf);
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
    <div style={{ maxWidth: 900 }}>
      <Title level={1}>Обратная связь и портфолио</Title>
      <Text type="secondary">Благодарности коллег и журнал достижений.</Text>

      {error ? <Alert type="error" message={error} showIcon style={{ margin: "16px 0" }} /> : null}

      <Spin spinning={loading}>
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24} lg={12}>
            <Card title="Лента благодарностей" variant="outlined">
              {praises.length === 0 ? (
                <Empty description="Пока нет благодарностей" />
              ) : (
                praises.map((p) => (
                  <div
                    key={p.id}
                    style={{
                      marginBottom: 12,
                      paddingBottom: 12,
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <Text strong>{p.sender_name ?? "Аноним"}</Text>
                    <Text type="secondary"> → {p.recipient_name}</Text>
                    <p style={{ marginTop: 4 }}>{p.message}</p>
                  </div>
                ))
              )}
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card title="Портфолио" variant="outlined">
              {portfolio.length === 0 ? (
                <Empty description="Пока нет записей" />
              ) : (
                <Timeline
                  items={portfolio.map((e) => ({
                    children: (
                      <>
                        <Tag>{PORTFOLIO_TYPE_LABELS[e.type] ?? e.type}</Tag>
                        <Text strong>{e.title}</Text>
                        {e.description ? <p style={{ marginTop: 4 }}>{e.description}</p> : null}
                      </>
                    ),
                  }))}
                />
              )}
            </Card>
          </Col>
        </Row>
      </Spin>
    </div>
  );
}
