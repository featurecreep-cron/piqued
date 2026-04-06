/**
 * Topic tags are stored snake_case in the DB so they're stable filter keys
 * (`securities_fraud_humor` is the same identity across articles regardless
 * of how we display it). This helper turns them into Title Case for display.
 *
 * Always render via humanizeTag() in user-facing UI. The raw value stays as
 * the filter key everywhere it's used as a Set member, store key, or query
 * parameter.
 */
export function humanizeTag(tag: string): string {
  if (!tag) return tag
  return tag
    .split('_')
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : ''))
    .join(' ')
}
