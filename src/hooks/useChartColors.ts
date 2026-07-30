import { useEffect, useState } from 'react';
import { getChartColors, type ChartColors } from '@/lib/chartColors';

/**
 * Chart colours for the active theme, re-read whenever the theme flips.
 *
 * Watches the `dark` class on the document element rather than consuming
 * ThemeProvider, deliberately: charts render inside test harnesses, and a hook
 * that throws "must be used within a ThemeProvider" would take the chart down
 * with it. This works in any tree, provider or not.
 *
 *   const c = useChartColors();
 *   <Bar dataKey="pnl">
 *     {rows.map(r => <Cell key={r.id} fill={c.forValue(r.pnl)} />)}
 *   </Bar>
 */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(getChartColors);

  useEffect(() => {
    if (typeof MutationObserver === 'undefined' || typeof document === 'undefined') return;

    const root = document.documentElement;
    let last = root.className;

    const observer = new MutationObserver(() => {
      // Only re-read when the class actually changed — the observer also fires
      // for unrelated attribute writes on the root element.
      if (root.className === last) return;
      last = root.className;
      setColors(getChartColors());
    });

    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  return colors;
}
