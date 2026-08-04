/**
 * Offset-paginated reads — the "load more" lists.
 *
 * Journal and Reports both accumulated pages by hand: an `offset` in state, a
 * `hasMore` flag, and a setter that appended to the previous array. That works,
 * but it throws the accumulated list away on unmount, so scrolling back to a list
 * you had already paged through starts again at page one.
 *
 * useInfiniteQuery keeps the pages, so returning to the list restores everything
 * that was loaded — and, like the rest of useApiQuery, it carries the abort signal
 * so a superseded request cannot land after a newer one.
 *
 * `getItems` tells the hook where the rows live in the response, since the two
 * endpoints disagree (`entries` vs `reports`). A page shorter than pageSize means
 * the end — the same rule the manual `hasMore` used.
 */
import { useInfiniteQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

type Params = Record<string, string | number | boolean | undefined | null>;

export function useApiInfiniteQuery<TPage, TItem>(
  key: readonly unknown[],
  url: string,
  options: {
    pageSize: number;
    getItems: (page: TPage) => TItem[];
    params?: Params;
    enabled?: boolean;
  },
) {
  const { pageSize, getItems, params, enabled } = options;

  const query = useInfiniteQuery<TPage>({
    queryKey: params ? [...key, params] : key,
    initialPageParam: 0,
    enabled,
    queryFn: async ({ pageParam, signal }) => {
      const res = await api.get<TPage>(url, {
        params: { ...params, limit: pageSize, offset: pageParam as number },
        signal,
      });
      return res.data;
    },
    getNextPageParam: (lastPage, allPages) => {
      const rows = getItems(lastPage);
      // A short page is the last page. Returning undefined is what sets
      // hasNextPage to false — returning a number unconditionally would page
      // forever against an endpoint that just keeps answering with an empty list.
      if (rows.length < pageSize) return undefined;
      return allPages.reduce((n, p) => n + getItems(p).length, 0);
    },
  });

  // Flattened once here so callers do not each re-derive it and drift on the
  // shape of `pages`.
  const items = (query.data?.pages ?? []).flatMap(getItems);

  return { ...query, items };
}
