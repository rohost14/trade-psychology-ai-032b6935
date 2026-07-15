import { useState, useEffect } from "react";

export interface Tick {
  last: number;
  changePct: number;
}

const entryPrices = {
  RELIANCE: 2487.4,
  INFY: 1521.6,
  NIFTY: 22486.2,
};

const currentPrices = {
  RELIANCE: 2487.4,
  INFY: 1521.6,
  NIFTY: 22486.2,
};

const histories: Record<string, number[]> = {
  RELIANCE: [2485.4, 2487.2, 2486.1, 2487.8, 2487.4],
  INFY: [1522.6, 1520.4, 1521.8, 1520.9, 1521.6],
  NIFTY: [22482.2, 22485.5, 22483.1, 22486.9, 22486.2],
};

export function getHistory(symbol: string): number[] {
  return histories[symbol] || [];
}

export function useTickStream() {
  const [ticks, setTicks] = useState<Record<string, Tick>>({
    NIFTY: { last: currentPrices.NIFTY, changePct: 0.42 },
    RELIANCE: { last: currentPrices.RELIANCE, changePct: 0 },
    INFY: { last: currentPrices.INFY, changePct: 0 },
  });

  useEffect(() => {
    const updateTick = (symbol: keyof typeof currentPrices, baseVolatility: number) => {
      const oldPrice = currentPrices[symbol];
      const change = (Math.random() - 0.495) * baseVolatility;
      const newPrice = oldPrice * (1 + change / 100);
      currentPrices[symbol] = newPrice;

      const hist = histories[symbol];
      hist.push(newPrice);
      if (hist.length > 8) {
        hist.shift();
      }

      const entry = entryPrices[symbol];
      const changePct = ((newPrice - entry) / entry) * 100;

      return { last: newPrice, changePct };
    };

    const interval = setInterval(() => {
      const nifty = updateTick("NIFTY", 0.04);
      const reliance = updateTick("RELIANCE", 0.06);
      const infy = updateTick("INFY", 0.1);

      setTicks({
        NIFTY: nifty,
        RELIANCE: reliance,
        INFY: infy,
      });
    }, 1500);

    return () => clearInterval(interval);
  }, []);

  return ticks;
}
