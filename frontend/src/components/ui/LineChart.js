import React from "react";

// 외부 라이브러리 없이 구현한 SVG 라인차트
// data: [{ label, value, anomaly? }]
export default function LineChart({ data = [], height = 220 }) {
  const width = 640;
  const padX = 36;
  const padY = 24;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;

  if (data.length === 0) {
    return <div className="chart"><p>조회된 데이터가 없습니다.</p></div>;
  }

  const values = data.map((d) => d.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  // 위아래 여유를 둬 선이 가장자리에 붙지 않도록 함
  const range = max - min || 1;
  const top = max + range * 0.15;
  const bottom = min - range * 0.15;
  const span = top - bottom;

  const xAt = (i) =>
    data.length === 1 ? padX + innerW / 2 : padX + (innerW * i) / (data.length - 1);
  const yAt = (v) => padY + innerH * (1 - (v - bottom) / span);

  const linePoints = data.map((d, i) => `${xAt(i)},${yAt(d.value)}`).join(" ");
  const areaPoints = `${padX},${padY + innerH} ${linePoints} ${padX + innerW},${
    padY + innerH
  }`;

  // 가로 격자선 (4등분)
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((t) => padY + innerH * t);

  return (
    <div className="chart linechart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="시계열 추이 라인 차트"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="wcm-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#141414" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#141414" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* 격자선 */}
        {gridLines.map((y, i) => (
          <line
            key={i}
            className="linechart__grid-line"
            x1={padX}
            y1={y}
            x2={padX + innerW}
            y2={y}
          />
        ))}

        {/* 면 그라데이션 */}
        <polygon points={areaPoints} fill="url(#wcm-area)" />

        {/* 라인 */}
        <polyline
          points={linePoints}
          fill="none"
          stroke="#141414"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* 데이터 포인트 (이상치는 강조) */}
        {data.map((d, i) => (
          <g key={i}>
            <circle
              className={d.anomaly ? "linechart__anomaly" : "linechart__point"}
              cx={xAt(i)}
              cy={yAt(d.value)}
              r={d.anomaly ? 6 : 4}
            />
            {d.anomaly && (
              <circle
                cx={xAt(i)}
                cy={yAt(d.value)}
                r="11"
                fill="none"
                stroke="#9b2c2c"
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
            )}
            {/* x축 라벨 */}
            <text
              className="linechart__axis-label"
              x={xAt(i)}
              y={height - 6}
              textAnchor="middle"
            >
              {d.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
