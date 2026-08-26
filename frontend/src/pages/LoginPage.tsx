/**
 * Страница входа (SPEC §14.1 — единая страница логина).
 *
 * Вход по AD-имени или email + пароль (LDAP с локальным fallback, SPEC §10.2).
 * Тон голоса — BRANDBOOK §9 (ясный, поддерживающий).
 */
import { Alert, App, Button, Card, Form, Input, Typography, type FormProps } from "antd";
import { useState } from "react";

import { toApiError } from "@/api/client";
import { Logo } from "@/components/Logo";
import { useAuth } from "@/app/auth-context";
import { getLoginErrorMessage } from "./login-error";

const { Title, Text } = Typography;

type LoginForm = { identifier: string; password: string };

export function LoginPage(): React.JSX.Element {
  const { signIn } = useAuth();
  const { message } = App.useApp();
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const onFinish: FormProps<LoginForm>["onFinish"] = async (values) => {
    setSubmitting(true);
    setFormError(null);
    try {
      await signIn(values.identifier, values.password);
      message.success("Вход выполнен");
    } catch (error) {
      setFormError(getLoginErrorMessage(toApiError(error)));
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
            name="identifier"
            label="Корпоративная учётная запись или email"
            rules={[{ required: true, message: "Введите учётную запись или email" }]}
          >
            <Input placeholder="a.ivanova" autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            label="Пароль"
            rules={[{ required: true, message: "Введите пароль" }]}
          >
            <Input.Password placeholder="Пароль" autoComplete="current-password" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 8 }}>
            <Button type="primary" htmlType="submit" block loading={submitting}>
              Войти
            </Button>
          </Form.Item>
        </Form>

        <Text type="secondary" style={{ display: "block", textAlign: "center" }}>
          Используйте учётную запись Active Directory или разрешённый локальный email.
        </Text>
      </Card>
    </div>
  );
}
