/**
 * Страница входа (SPEC §14.1 — единая страница логина).
 *
 * Вход по email + пароль (запасной механизм, SPEC §10.2). SSO-кнопка —
 * расширяемая заглушка (тип SSO уточняется, SPEC §17 п.2).
 * Тон голоса — BRANDBOOK §9 (ясный, поддерживающий).
 */
import { LockOutlined, MailOutlined } from "@ant-design/icons";
import { Alert, App, Button, Card, Form, Input, Typography, type FormProps } from "antd";
import { useState } from "react";

import { Logo } from "@/components/Logo";
import { useAuth } from "@/app/auth-context";

const { Title, Text } = Typography;

type LoginForm = { email: string; password: string };

export function LoginPage(): React.JSX.Element {
  const { signIn } = useAuth();
  const { message } = App.useApp();
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const onFinish: FormProps<LoginForm>["onFinish"] = async (values) => {
    setSubmitting(true);
    setFormError(null);
    try {
      await signIn(values.email, values.password);
      message.success("Вход выполнен");
    } catch {
      setFormError("Неверный email или пароль. Проверьте данные и попробуйте снова.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-base)",
        padding: 16,
      }}
    >
      <Card
        style={{
          width: "100%",
          maxWidth: 400,
          boxShadow: "var(--elevation-2)",
          borderRadius: "var(--radius-lg)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div style={{ color: "var(--color-primary)", display: "inline-flex" }}>
            <Logo size={40} withWordmark={false} />
          </div>
          <Title level={2} style={{ marginTop: 12, marginBottom: 4 }}>
            Вход в Vektor
          </Title>
          <Text type="secondary">Оценка, обучение и развитие</Text>
        </div>

        {formError ? (
          <Alert type="error" message={formError} showIcon style={{ marginBottom: 16 }} />
        ) : null}

        <Form<LoginForm> layout="vertical" onFinish={onFinish} autoComplete="on">
          <Form.Item
            name="email"
            label="Корпоративный email"
            rules={[
              { required: true, message: "Введите email" },
              { type: "email", message: "Некорректный email" },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="you@company.ru" autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            label="Пароль"
            rules={[{ required: true, message: "Введите пароль" }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Пароль"
              autoComplete="current-password"
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 8 }}>
            <Button type="primary" htmlType="submit" block loading={submitting}>
              Войти
            </Button>
          </Form.Item>
        </Form>

        {/* TODO(#6, SPEC §17 п.2): кнопка SSO — тип уточняется (SAML/OIDC/LDAP). */}
        <Text type="secondary" style={{ display: "block", textAlign: "center" }}>
          Вход через корпоративную учётную запись будет добавлен после настройки SSO.
        </Text>
      </Card>
    </div>
  );
}
