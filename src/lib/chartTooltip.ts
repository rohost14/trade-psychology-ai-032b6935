/**
 * Minimal typing for recharts custom-tooltip props.
 *
 * Recharts passes many more fields, but custom tooltips only ever read
 * `active` and the row behind `payload[0].payload` — typing just that
 * removes the `any` escape hatch without fighting recharts' generics.
 */
export interface ChartTooltipProps<T> {
  active?: boolean;
  payload?: ReadonlyArray<{ payload: T }>;
}
