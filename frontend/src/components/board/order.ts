// The board's one piece of arithmetic (§6.5, §15), kept pure so order.test.mjs can run it in Node.

/**
 * Move one item up (`by` = -1) or down (`by` = +1). A move that would leave the list is no move,
 * so the caller can hand any index in and get a list back either way.
 */
export function reorder<T>(list: T[], from: number, by: number): T[] {
  const to = from + by
  if (from < 0 || from >= list.length || to < 0 || to >= list.length) return list
  const next = [...list]
  ;[next[from], next[to]] = [next[to], next[from]]
  return next
}
