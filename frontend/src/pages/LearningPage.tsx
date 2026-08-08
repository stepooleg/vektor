/**
 * Модуль обучения — каталог курсов (SPEC §7.1, §14.3, issue #25).
 *
 * Карточки курсов (BRANDBOOK §6.5), фильтр по категории, поиск.
 * Цвета — только дизайн-токены (BRANDBOOK §10.2).
 */
import { Alert, Card, Col, Empty, Input, Row, Select, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";

import {
  type Course,
  type CourseCategory,
  type CourseFilter,
  getCourses,
  getCourseCategories,
} from "@/api/lms";
import { toApiError } from "@/api/client";

const { Title, Text } = Typography;

export function LearningPage(): React.JSX.Element {
  const [courses, setCourses] = useState<Course[]>([]);
  const [categories, setCategories] = useState<CourseCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState<number | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    getCourseCategories()
      .then((data) => {
        if (!cancelled) setCategories(data);
      })
      .catch(() => {
        /* категории опциональны */
      });
    return () => {
      cancelled = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const filter: CourseFilter = {};
    if (search) filter.search = search;
    if (categoryId) filter.category = categoryId;
    getCourses(filter)
      .then((data) => {
        if (!cancelled) setCourses(data);
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
  }, [search, categoryId]);

  return (
    <div style={{ maxWidth: 1000 }}>
      <Title level={1}>Обучение</Title>
      <Text type="secondary">Каталог курсов и личный кабинет обучения.</Text>

      <Row gutter={12} style={{ margin: "16px 0" }}>
        <Col flex="auto">
          <Input.Search
            placeholder="Поиск по названию…"
            allowClear
            onSearch={(v) => setSearch(v)}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder="Категория"
            style={{ width: 200 }}
            value={categoryId}
            onChange={(v) => setCategoryId(v ?? undefined)}
            options={categories.map((c) => ({ value: c.id, label: c.name }))}
          />
        </Col>
      </Row>

      {error ? <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} /> : null}

      <Spin spinning={loading}>
        {courses.length === 0 && !loading ? (
          <Empty description="Курсы не найдены" />
        ) : (
          <Row gutter={[16, 16]}>
            {courses.map((course) => (
              <Col xs={24} sm={12} lg={8} key={course.id}>
                <Card hoverable title={course.title} bordered style={{ height: "100%" }}>
                  <p>
                    <Text type="secondary" ellipsis>
                      {course.description || "Без описания"}
                    </Text>
                  </p>
                  {course.is_mandatory ? (
                    <Tag color="warning">Обязательный</Tag>
                  ) : (
                    <Tag>Добровольный</Tag>
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
