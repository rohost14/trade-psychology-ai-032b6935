import * as React from "react";
import { cn } from "@/lib/utils";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  className?: string;
  stroke?: string;
  strokeWidth?: number;
}

export default function Sparkline({
  data,
  width = 88,
  height = 22,
  className,
  stroke,
  strokeWidth
}: SparklineProps) {
  const pathD = React.useMemo(() => {
    if (!data || data.length < 2) return "";
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min === 0 ? 1 : max - min;
    const points = data.map((val, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - ((val - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return "M" + points.join(" L");
  }, [data, width, height]);

  const resolvedStroke = React.useMemo(() => {
    if (stroke) return stroke;
    if (!data || data.length < 2) return "#10b981";
    return data[data.length - 1] >= data[0] ? "#10b981" : "#ef4444";
  }, [stroke, data]);

  if (!data || data.length === 0) return null;

  return (
    <svg
      width={width}
      height={height}
      className={cn("overflow-visible", className)}
    >
      <path
        d={pathD}
        fill="none"
        stroke={resolvedStroke}
        strokeWidth={strokeWidth ?? (width > 50 ? 1.5 : 1.2)}
      />
    </svg>
  );
}
