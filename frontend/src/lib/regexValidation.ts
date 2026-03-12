/**
 * Regex validation utilities to prevent ReDoS (Regular Expression Denial of Service).
 *
 * Mirrors the backend validation in adapters/persistence/repositories/regex_utils.py.
 */

const MAX_REGEX_LENGTH = 500

/**
 * Patterns that can cause catastrophic backtracking (ReDoS).
 * These detect nested quantifiers like (.*)+, (.+)+, (x+)+, (x*)+, (x+)*, (x*)*.
 */
const DANGEROUS_REGEX_PATTERNS: RegExp[] = [
  /\(\.\*\)\+/, // (.*)+
  /\(\.\+\)\+/, // (.+)+
  /\([^)]*\+\)\+/, // (x+)+
  /\([^)]*\*\)\+/, // (x*)+
  /\([^)]*\+\)\*/, // (x+)*
  /\([^)]*\*\)\*/, // (x*)*
]

export interface RegexValidationResult {
  valid: boolean
  error?: string
}

/**
 * Validate a regex pattern for safety before compilation.
 *
 * Checks:
 * 1. Length limit (max 500 characters)
 * 2. Dangerous nested quantifier patterns (ReDoS)
 * 3. Valid syntax (via RegExp constructor)
 */
export function validateRegexPattern(pattern: string): RegexValidationResult {
  if (pattern.length > MAX_REGEX_LENGTH) {
    return {
      valid: false,
      error: `Regex pattern too long: ${pattern.length} characters (max ${MAX_REGEX_LENGTH})`,
    }
  }

  for (const dangerous of DANGEROUS_REGEX_PATTERNS) {
    if (dangerous.test(pattern)) {
      return {
        valid: false,
        error:
          'Regex pattern contains potentially dangerous nested quantifiers that could cause performance issues',
      }
    }
  }

  try {
    new RegExp(pattern)
  } catch (e) {
    return {
      valid: false,
      error: `Invalid regex pattern: ${e instanceof Error ? e.message : String(e)}`,
    }
  }

  return { valid: true }
}
