const LETTERS = "BIUROKRATKA";
const STEP = 95;

/** Linear mark (11 cells in a row) from the brand book; "KRATKA" cells are filled with the accent. */
export function Logo({ width = 176 }: { width?: number }) {
  const w = STEP * LETTERS.length + 5;
  return (
    <svg
      viewBox={`0 0 ${w} 120`}
      width={width}
      role="img"
      aria-label="Biurokratka"
      style={{ display: "block", height: "auto" }}
    >
      {[...LETTERS].map((letter, i) => {
        const x = i * STEP;
        const filled = i >= 5;
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: static letters
          <g key={i}>
            {filled ? (
              <rect x={x} y="0" width="100" height="120" fill="var(--color-accent)" />
            ) : null}
            <rect
              x={x + 2.5}
              y="2.5"
              width="95"
              height="115"
              fill="none"
              stroke="var(--color-text)"
              strokeWidth="5"
            />
            <text
              x={x + 50}
              y="60"
              textAnchor="middle"
              dominantBaseline="central"
              fontFamily="Archivo, sans-serif"
              fontWeight="600"
              fontSize="75"
              fill="var(--color-text)"
            >
              {letter}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
