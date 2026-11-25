// Dates from the API are plain YYYY-MM-DD (or ISO timestamps). Read the date
// part as a local calendar date, so "2027-03-01" never shows as Feb 28.
export function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
