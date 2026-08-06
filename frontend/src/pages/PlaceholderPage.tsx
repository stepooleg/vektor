/**
 * Страница-заглушка для разделов каркаса (Phase 0).
 * Заменяется полноценными экранами в соответствующих фазах (SPEC §14).
 */
import { Typography } from "antd";

const { Title, Paragraph } = Typography;

interface PlaceholderPageProps {
  /** Название раздела. */
  title: string;
  /** Краткое описание (тон голоса — BRANDBOOK §9). */
  description?: string;
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps): React.JSX.Element {
  return (
    <div style={{ maxWidth: 720 }}>
      <Title level={1}>{title}</Title>
      <Paragraph type="secondary">
        {description ?? "Этот раздел будет реализован в следующих фазах разработки."}
      </Paragraph>
    </div>
  );
}
