import React, { useId } from "react";

// data: [{ label, value, anomaly?, includedRows? }]
export default function LineChart({ data = [], height = 220, showValues = false, valueSuffix = "" }) {
  const gradientId = `wcm-area-${useId().replace(/:/g, "")}`;
  const items = Array.isArray(data) ? data : [];
  const width = 640;
  const chartHeight =
    typeof height === "number" && Number.isFinite(height)
      ? Math.max(height, 100)
      : 220;

  const padX = 36;
  const padY = showValues ? 30 : 24;
  const innerW = width - padX * 2;
  const innerH = chartHeight - padY * 2;

  const isValid = (item) =>
    item != null &&
    typeof item.value === "number" &&
    Number.isFinite(item.value);

  const values = items.filter(isValid).map((item) => item.value);

  if (items.length === 0) {
    return (
      <div className="chart">
        <p>조회된 데이터가 없습니다.</p>
      </div>
    );
  }

  if (values.length === 0) {
    return (
      <div className="chart">
        <p>표시할 값이 없습니다.</p>
      </div>
    );
  }

  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const top = max + range * 0.15;
  const bottom = min - range * 0.15;
  const span = top - bottom;

  const xAt = (index) =>
    items.length === 1
      ? padX + innerW / 2
      : padX + (innerW * index) / (items.length - 1);

  const yAt = (value) =>
    padY + innerH * (1 - (value - bottom) / span);

  // 결측 지점마다 선과 면을 나눈다.
  const segments = [];
  let currentSegment = [];

  items.forEach((item, index) => {
    if (isValid(item)) {
      currentSegment.push({
        x: xAt(index),
        y: yAt(item.value),
      });
    } else if (currentSegment.length > 0) {
      segments.push(currentSegment);
      currentSegment = [];
    }
  });

  if (currentSegment.length > 0) {
    segments.push(currentSegment);
  }

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map(
    (fraction) => padY + innerH * fraction
  );

  // 긴 날짜가 겹치지 않도록 축에는 최대 약 8개만 표시한다.
  // 모든 기록의 날짜와 값은 각 점의 툴팁에서 확인할 수 있다.
  const hasDateLabels = items.some((item) => /^\d{4}-\d{2}-\d{2}$/.test(item?.label || ""));
  const labelCount = Math.min(items.length, hasDateLabels ? 6 : 8);
  const labelIndices = new Set(
    Array.from({ length: labelCount }, (_, index) =>
      labelCount === 1 ? 0 : Math.round(index * (items.length - 1) / (labelCount - 1))
    )
  );

  return (
    <div className="chart linechart">
      <svg
        viewBox={`0 0 ${width} ${chartHeight}`}
        role="img"
        aria-label="시계열 추이 라인 차트"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient
            id={gradientId}
            x1="0"
            y1="0"
            x2="0"
            y2="1"
          >
            <stop offset="0%" stopColor="#141414" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#141414" stopOpacity="0" />
          </linearGradient>
        </defs>

        {gridLines.map((y, index) => (
          <line
            key={index}
            className="linechart__grid-line"
            x1={padX}
            y1={y}
            x2={padX + innerW}
            y2={y}
          />
        ))}

        {segments.map((segment, index) => {
          if (segment.length < 2) return null;

          const points = segment
            .map((point) => `${point.x},${point.y}`)
            .join(" ");

          const first = segment[0];
          const last = segment[segment.length - 1];
          const areaPoints =
            `${first.x},${padY + innerH} ` +
            `${points} ${last.x},${padY + innerH}`;

          return (
            <g key={`segment-${index}`}>
              <polygon
                points={areaPoints}
                fill={`url(#${gradientId})`}
              />
              <polyline
                points={points}
                fill="none"
                stroke="#141414"
                strokeWidth="2.5"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            </g>
          );
        })}

        {items.map((item, index) => {
          const valid = isValid(item);
          const showLabel =
            labelIndices.has(index);

          const countText =
            Number.isInteger(item?.includedRows) &&
            item.includedRows >= 0
              ? ` · 포함 ${item.includedRows.toLocaleString()}건`
              : "";

          return (
            <g key={`point-${index}`}>
              {valid && (
                <>
                  <circle
                    className={
                      item.anomaly
                        ? "linechart__anomaly"
                        : "linechart__point"
                    }
                    cx={xAt(index)}
                    cy={yAt(item.value)}
                    r={item.anomaly ? 6 : 4}
                  >
                    <title>
                      {`${item.label ?? ""}: ${item.value}${countText}`}
                    </title>
                  </circle>

                  {item.anomaly && (
                    <circle
                      cx={xAt(index)}
                      cy={yAt(item.value)}
                      r="11"
                      fill="none"
                      stroke="#9b2c2c"
                      strokeWidth="1.5"
                      strokeDasharray="3 3"
                    />
                  )}
                </>
              )}

              {showValues && valid && showLabel && (
                <text
                  className="linechart__value-label"
                  x={xAt(index)}
                  y={yAt(item.value) - (item.anomaly ? 15 : 9)}
                  textAnchor="middle"
                  aria-hidden="true"
                >
                  {item.value.toLocaleString("ko-KR")}{valueSuffix}
                </text>
              )}

              {showLabel && (
                <text
                  className="linechart__axis-label"
                  x={xAt(index)}
                  y={chartHeight - 6}
                  textAnchor={items.length === 1 ? "middle" : index === 0 ? "start" : index === items.length - 1 ? "end" : "middle"}
                >
                  {item?.label ?? ""}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}