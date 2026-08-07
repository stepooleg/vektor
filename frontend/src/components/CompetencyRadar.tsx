/**
 * Радар компетенций (Recharts, SPEC §9.2, BRANDBOOK §3.4).
 *
 * Цвета — только дизайн-токены графиков (chart-* из tokens.css).
 * Отображает агрегированный профиль компетенций сотрудника.
 */
import { Empty } from "antd";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from "recharts";

import type { CompetencyProfileRow } from "@/api/analytics";

interface CompetencyRadarProps {
  /** Профиль компетенций (агрегаты). */
  profile: CompetencyProfileRow[];
  /** Высота контейнера в пикселях. */
  height?: number;
}

export function CompetencyRadar({
  profile,
  height = 320,
}: CompetencyRadarProps): React.JSX.Element {
  if (profile.length === 0) {
    return <Empty description="Пока нет данных по компетенциям" />;
  }

  const data = profile.map((row) => ({
    name: row.competency_name,
    score: row.mean_score,
  }));

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis dataKey="name" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
          <Radar
            name="Профиль"
            dataKey="score"
            stroke="var(--chart-primary)"
            fill="var(--chart-primary)"
            fillOpacity={0.4}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
