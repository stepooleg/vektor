/** Интерактивный кабинет обучения (SPEC §7, §14.3, issue #68). */
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Input,
  Modal,
  Progress,
  Radio,
  Row,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";

import {
  completeLesson,
  type Course,
  type CourseCategory,
  type CourseFilter,
  ENROLLMENT_STATUS_LABELS,
  enrollInCourse,
  getCourse,
  getCourseCategories,
  getCourses,
  getMyLearning,
  type Enrollment,
  submitQuiz,
} from "@/api/lms";
import { toApiError } from "@/api/client";

const { Paragraph, Text, Title } = Typography;

function replaceEnrollment(items: Enrollment[], next: Enrollment): Enrollment[] {
  const exists = items.some((item) => item.id === next.id);
  return exists ? items.map((item) => (item.id === next.id ? next : item)) : [next, ...items];
}

export function LearningPage(): React.JSX.Element {
  const [courses, setCourses] = useState<Course[]>([]);
  const [categories, setCategories] = useState<CourseCategory[]>([]);
  const [myLearning, setMyLearning] = useState<Enrollment[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<Course | null>(null);
  const [answers, setAnswers] = useState<Record<number, number[]>>({});
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState<number | undefined>(undefined);

  const selectedEnrollment = useMemo(
    () => myLearning.find((item) => item.course.id === selectedCourse?.id),
    [myLearning, selectedCourse],
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCourseCategories(), getMyLearning()])
      .then(([categoryData, learningData]) => {
        if (!cancelled) {
          setCategories(categoryData);
          setMyLearning(learningData);
        }
      })
      .catch(() => {
        // Категории и личный кабинет не блокируют загрузку каталога.
      });
    return () => {
      cancelled = true;
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
      .catch((reason: unknown) => {
        if (!cancelled) setError(toApiError(reason).detail);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [search, categoryId]);

  async function openCourse(courseId: number): Promise<void> {
    setDetailLoading(true);
    setError(null);
    setNotice(null);
    try {
      setSelectedCourse(await getCourse(courseId));
      setAnswers({});
    } catch (reason) {
      setError(toApiError(reason).detail);
    } finally {
      setDetailLoading(false);
    }
  }

  async function enroll(): Promise<void> {
    if (!selectedCourse) return;
    setActionLoading(true);
    try {
      const enrollment = await enrollInCourse(selectedCourse.id);
      setMyLearning((current) => replaceEnrollment(current, enrollment));
      setNotice("Вы записаны на курс");
    } catch (reason) {
      setError(toApiError(reason).detail);
    } finally {
      setActionLoading(false);
    }
  }

  async function finishTextLesson(lessonId: number): Promise<void> {
    if (!selectedCourse) return;
    setActionLoading(true);
    try {
      const enrollment = await completeLesson(selectedCourse.id, lessonId);
      setMyLearning((current) => replaceEnrollment(current, enrollment));
      setNotice("Прогресс сохранён");
    } catch (reason) {
      setError(toApiError(reason).detail);
    } finally {
      setActionLoading(false);
    }
  }

  async function finishQuiz(lessonId: number): Promise<void> {
    if (!selectedCourse) return;
    setActionLoading(true);
    try {
      const response = await submitQuiz(selectedCourse.id, lessonId, answers);
      setMyLearning((current) => replaceEnrollment(current, response.enrollment));
      setNotice(
        response.result.passed
          ? `Тест пройден: ${response.result.percent}%`
          : `Тест не пройден: ${response.result.percent}%. Попробуйте ещё раз.`,
      );
    } catch (reason) {
      setError(toApiError(reason).detail);
    } finally {
      setActionLoading(false);
    }
  }

  const catalog = (
    <>
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col flex="auto">
          <Input.Search
            placeholder="Поиск по названию…"
            allowClear
            onSearch={(value) => setSearch(value)}
          />
        </Col>
        <Col>
          <Select
            allowClear
            aria-label="Категория"
            placeholder="Категория"
            style={{ width: 200 }}
            value={categoryId}
            onChange={(value) => setCategoryId(value ?? undefined)}
            options={categories.map((category) => ({
              value: category.id,
              label: category.name,
            }))}
          />
        </Col>
      </Row>
      <Spin spinning={loading}>
        {courses.length === 0 && !loading ? (
          <Empty description="Курсы не найдены" />
        ) : (
          <Row gutter={[16, 16]}>
            {courses.map((course) => (
              <Col xs={24} sm={12} lg={8} key={course.id}>
                <Card
                  title={course.title}
                  variant="outlined"
                  style={{ height: "100%" }}
                  actions={[
                    <Button type="link" key="open" onClick={() => void openCourse(course.id)}>
                      Открыть курс
                    </Button>,
                  ]}
                >
                  <Paragraph type="secondary" ellipsis={{ rows: 2 }}>
                    {course.description || "Без описания"}
                  </Paragraph>
                  <Tag>{course.is_mandatory ? "Обязательный" : "Добровольный"}</Tag>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </>
  );

  const personal =
    myLearning.length === 0 ? (
      <Empty description="Вы ещё не записаны на курсы" />
    ) : (
      <Row gutter={[16, 16]}>
        {myLearning.map((enrollment) => (
          <Col xs={24} md={12} key={enrollment.id}>
            <Card
              title={enrollment.course.title}
              extra={<Tag>{ENROLLMENT_STATUS_LABELS[enrollment.status] ?? enrollment.status}</Tag>}
            >
              <Progress percent={enrollment.progress_percent} />
              <Paragraph>{enrollment.progress_percent}% завершено</Paragraph>
              {enrollment.certificate ? (
                <Alert
                  type="success"
                  showIcon
                  message={`Сертификат ${enrollment.certificate.code}`}
                />
              ) : null}
              <Button
                style={{ marginTop: 12 }}
                onClick={() => void openCourse(enrollment.course.id)}
              >
                {enrollment.status === "completed" ? "Посмотреть курс" : "Продолжить"}
              </Button>
            </Card>
          </Col>
        ))}
      </Row>
    );

  return (
    <div style={{ maxWidth: 1000 }}>
      <Title level={1}>Обучение</Title>
      <Text type="secondary">Каталог курсов и личный кабинет обучения.</Text>
      {error ? <Alert type="error" message={error} showIcon style={{ marginTop: 16 }} /> : null}
      <Tabs
        style={{ marginTop: 16 }}
        items={[
          { key: "catalog", label: "Каталог", children: catalog },
          { key: "my", label: "Моё обучение", children: personal },
        ]}
      />

      <Modal
        open={selectedCourse !== null || detailLoading}
        width={760}
        footer={null}
        onCancel={() => setSelectedCourse(null)}
        destroyOnHidden
      >
        <Spin spinning={detailLoading}>
          {selectedCourse ? (
            <Space direction="vertical" size="large" style={{ width: "100%" }}>
              <div>
                <Title level={2}>{selectedCourse.title}</Title>
                <Paragraph>
                  {selectedCourse.description || "Описание курса пока не добавлено."}
                </Paragraph>
                {!selectedEnrollment ? (
                  <Button type="primary" loading={actionLoading} onClick={() => void enroll()}>
                    Записаться на курс
                  </Button>
                ) : (
                  <Progress percent={selectedEnrollment.progress_percent} />
                )}
              </div>
              {notice ? <Alert type="success" showIcon message={notice} /> : null}
              <div>
                <Title level={3}>Программа курса</Title>
                <Space direction="vertical" style={{ width: "100%" }}>
                  {selectedCourse.lessons.map((lesson) => {
                    const lessonProgress = selectedEnrollment?.lesson_progresses.find(
                      (item) => item.lesson === lesson.id,
                    );
                    return (
                      <Card
                        size="small"
                        key={lesson.id}
                        title={lesson.title}
                        extra={lessonProgress?.completed ? <Tag>Пройден</Tag> : null}
                      >
                        {lesson.type === "text" ? (
                          <>
                            <Paragraph>{lesson.content}</Paragraph>
                            {selectedEnrollment && !lessonProgress?.completed ? (
                              <Button
                                loading={actionLoading}
                                onClick={() => void finishTextLesson(lesson.id)}
                              >
                                Отметить пройденным
                              </Button>
                            ) : null}
                          </>
                        ) : (
                          <Space direction="vertical" style={{ width: "100%" }}>
                            {lesson.questions.map((question) => (
                              <div key={question.id}>
                                <Paragraph strong>{question.text}</Paragraph>
                                {question.type === "multiple" ? (
                                  <Checkbox.Group
                                    options={question.options.map((option) => ({
                                      label: option.text,
                                      value: option.id,
                                    }))}
                                    onChange={(values) =>
                                      setAnswers((current) => ({
                                        ...current,
                                        [question.id]: values.map(Number),
                                      }))
                                    }
                                  />
                                ) : (
                                  <Radio.Group
                                    options={question.options.map((option) => ({
                                      label: option.text,
                                      value: option.id,
                                    }))}
                                    onChange={(event) =>
                                      setAnswers((current) => ({
                                        ...current,
                                        [question.id]: [Number(event.target.value)],
                                      }))
                                    }
                                  />
                                )}
                              </div>
                            ))}
                            {selectedEnrollment && !lessonProgress?.completed ? (
                              <Button
                                type="primary"
                                loading={actionLoading}
                                onClick={() => void finishQuiz(lesson.id)}
                              >
                                Отправить ответы
                              </Button>
                            ) : null}
                          </Space>
                        )}
                      </Card>
                    );
                  })}
                </Space>
              </div>
            </Space>
          ) : null}
        </Spin>
      </Modal>
    </div>
  );
}
