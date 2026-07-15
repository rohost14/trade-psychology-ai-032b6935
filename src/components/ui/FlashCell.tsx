import * as React from "react";
import { cn } from "@/lib/utils";

interface FlashCellProps {
  value: number;
  format: (val: number) => string;
  className?: string;
}

export default function FlashCell({ value, format, className }: FlashCellProps) {
  const [flash, setFlash] = React.useState<"up" | "down" | null>(null);
  const prevValueRef = React.useRef<number>(value);

  React.useEffect(() => {
    const prev = prevValueRef.current;
    if (value !== prev) {
      setFlash(value > prev ? "up" : "down");
      prevValueRef.current = value;
      
      const timer = setTimeout(() => {
        setFlash(null);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [value]);

  return (
    <span
      className={cn(
        "transition-all duration-300",
        flash === "up" && "text-emerald-400 font-semibold bg-emerald-500/10 px-1 rounded",
        flash === "down" && "text-red-400 font-semibold bg-red-500/10 px-1 rounded",
        className
      )}
    >
      {format(value)}
    </span>
  );
}
