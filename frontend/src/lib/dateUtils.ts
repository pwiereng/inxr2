/**
 * Date parsing and formatting utilities for commit timestamps.
 *
 * Git commit dates are stored in UTC but may or may not include timezone indicators.
 * These utilities handle both cases robustly.
 */

/**
 * Regex to match ISO 8601 timezone suffixes:
 * - Z (Zulu/UTC)
 * - +HH:MM or -HH:MM (with colon)
 * - +HHMM or -HHMM (without colon)
 */
const ISO_8601_TZ_SUFFIX_RE = /(Z|[+-]\d{2}:?\d{2})$/i

/**
 * Check if a date string has a timezone indicator.
 */
export function hasTimezoneIndicator(dateString: string): boolean {
  return ISO_8601_TZ_SUFFIX_RE.test(dateString)
}

/**
 * Parse a date string as UTC.
 *
 * If the date string has no timezone indicator, it is treated as UTC
 * by appending 'Z'. This is the expected behavior for git commit dates
 * which are stored in UTC.
 */
export function parseAsUTC(dateString: string): Date {
  if (!hasTimezoneIndicator(dateString)) {
    return new Date(dateString + 'Z')
  }
  return new Date(dateString)
}

/**
 * Format a date string as YYYY-MM-DD in UTC.
 *
 * Returns an empty string for empty or invalid inputs.
 */
export function formatDateYMD(dateString: string): string {
  if (!dateString) return ''
  const date = parseAsUTC(dateString)
  if (isNaN(date.getTime())) return ''
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Format a commit date for display.
 *
 * Returns a compact date string in the format:
 * - "YYYYMMDD" if there's only one commit on that day
 * - "YYYYMMDD HH:MM UTC" if there are multiple commits on the same day
 *
 * @param dateString - The commit date string to format
 * @param allDates - Array of all commit dates to check for same-day commits
 */
export function formatCommitDate(dateString: string, allDates: string[]): string {
  const date = parseAsUTC(dateString)

  // Format as yyyymmdd in UTC
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  const dateStr = `${year}${month}${day}`

  // Check if there are other commits on the same day (in UTC)
  const sameDayCount = allDates.filter((d) => {
    const other = parseAsUTC(d)
    return (
      other.getUTCFullYear() === date.getUTCFullYear() &&
      other.getUTCMonth() === date.getUTCMonth() &&
      other.getUTCDate() === date.getUTCDate()
    )
  }).length

  // If multiple commits on same day, add time with UTC indicator
  if (sameDayCount > 1) {
    const hours = String(date.getUTCHours()).padStart(2, '0')
    const minutes = String(date.getUTCMinutes()).padStart(2, '0')
    return `${dateStr} ${hours}:${minutes} UTC`
  }

  return dateStr
}
