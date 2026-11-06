import React from "react";

// 외부 라이브러리 없이 구현한 SVG 라인차트
// data: [{ label, value, anomaly? }]
// props:
//  - showValues: 각 포인트 위에 값 라벨 표시
//  - showYAxis: 좌측 Y축 눈금값 표시
//  - valueFormatter: 값 표시 포맷 함수
export default function LineChart({
  data = [],
  height = 240,
  showValues = true,
  showYAxis = true,
  valueFormatter = (v) => v,
}) {
  const width = 640;
  const padX = showYAxis ? 48 : 36;
  const padY = 28;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;

  if (data.length === 0) {
    return (
      <div className="chart">
        <p className="chart__empty">조회된 데이터가 없습니다.</p>
      </div>
    );
  }

  const values = data.map((d) => d.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  // 위아래 여유를 둬 선이 가장자리에 붙지 않도록 함
  const range = max - min || 1;
  const top = max + range * 0.2;
  const bottom = min - range * 0.2;
  const span = top - bottom;

  const xAt = (i) =>
    data.length === 1 ? padX + innerW / 2 : padX + (innerW * i) / (data.length - 1);
  const yAt = (v) => padY + innerH * (1 - (v - bottom) / span);

  const linePoints = data.map((d, i) => `${xAt(i)},${yAt(d.value)}`).join(" ");
  const areaPoints = `${padX},${padY + innerH} ${linePoints} ${padX + innerW},${padY + innerH
    }`;

  // 가로 격자선 (4등분) + Y축 눈금값
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => {
    const y = padY + innerH * t;
    const v = top - span * t; // 위쪽이 큰 값
    return { y, v };
  });

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
            <stop offset="0%" stopColor="#141414" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#141414" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* 격자선 + Y축 눈금값 */}
        {ticks.map((tick, i) => (
          <g key={i}>
            <line
              className="linechart__grid-line"
              x1={padX}
              y1={tick.y}
              x2={padX + innerW}
              y2={tick.y}
            />
            {showYAxis && (
              <text
                className="linechart__axis-label"
                x={padX - 8}
                y={tick.y + 3}
                textAnchor="end"
              >
                {valueFormatter(Math.round(tick.v))}
              </text>
            )}
          </g>
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
        {data.map((d, i) => {
          const px = xAt(i);
          const py = yAt(d.value);
          return (
            <g key={i}>
              {d.anomaly && (
                <circle
                  cx={px}
                  cy={py}
                  r="12"
                  fill="none"
                  stroke="#9b2c2c"
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                />
              )}
              <circle
                className={d.anomaly ? "linechart__anomaly" : "linechart__point"}
                cx={px}
                cy={py}
                r={d.anomaly ? 6 : 4}
              />

              {/* 값 라벨 */}
              {showValues && (
                <text
                  className={`linechart__value ${d.anomaly ? "is-anomaly" : ""
                    }`.trim()}
                  x={px}
                  y={py - 12}
                  textAnchor="middle"
                >
                  {valueFormatter(d.value)}
                </text>
              )}

              {/* x축 라벨 */}
              <text
                className="linechart__axis-label"
                x={px}
                y={height - 6}
                textAnchor="middle"
              >
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
