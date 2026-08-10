/** Полный пользовательский сценарий оценки (SPEC §5, §14.2, issue #70). */
import { Typography } from "antd";

import { useAuth } from "@/app/auth-context";
import { CycleManager } from "@/features/assessment/CycleManager";
import { MyAssignments } from "@/features/assessment/MyAssignments";

const { Text, Title } = Typography;

export function AssessmentPage(): React.JSX.Element {
  const { user } = useAuth();
  const canManage = user?.roles.some((role) => role === "hr" || role === "manager") ?? false;

  return (
    <div style={{ maxWidth: 1000 }}>
      <Title level={1}>Оценка 360°</Title>
      <Text type="secondary">
        Заполняйте назначенные оценки и управляйте циклами в рамках своей роли.
      </Text>
      <MyAssignments />
      {canManage ? <CycleManager canManage /> : null}
    </div>
  );
}
