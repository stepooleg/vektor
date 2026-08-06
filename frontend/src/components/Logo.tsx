/**
 * Логотип Vektor (BRANDBOOK §2.1).
 *
 * Стилизованная стрелка-вектор, задающая направление вверх-вперёд.
 * Цвет наследуется от текущего текста (var(--color-primary)),
 * поэтому работает в обеих темах без хардкод-HEX.
 */
interface LogoProps {
  /** Размер знака в пикселях (BRANDBOOK §2.3: минимум 24px). */
  size?: number;
  /** Показывать ли слово «Vektor» рядом со знаком. */
  withWordmark?: boolean;
}

export function Logo({ size = 28, withWordmark = true }: LogoProps): React.JSX.Element {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }} className="vektor-logo">
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        role="img"
        aria-label="Vektor"
      >
        {/* Стрелка-вектор: восходящий Chevron, цвет из токена через currentColor. */}
        <path d="M16 4 L28 22 L22 22 L16 13 L10 22 L4 22 Z" fill="currentColor" />
      </svg>
      {withWordmark ? <span style={{ fontWeight: 700, fontSize: size * 0.7 }}>Vektor</span> : null}
    </span>
  );
}
