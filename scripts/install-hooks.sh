#!/bin/bash
# Install local git hooks for INXR2.
# Run once after cloning: ./scripts/install-hooks.sh
#
# Installs:
#   pre-commit  — gitleaks secret scan on staged files

set -e

HOOKS_DIR="$(git rev-parse --git-dir)/hooks"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Installing git hooks into $HOOKS_DIR..."

# ---------------------------------------------------------------------------
# gitleaks pre-commit hook
# ---------------------------------------------------------------------------
# Requires gitleaks to be installed: https://github.com/gitleaks/gitleaks
# macOS:  brew install gitleaks
# Linux:  https://github.com/gitleaks/gitleaks/releases

PRECOMMIT="$HOOKS_DIR/pre-commit"

cat > "$PRECOMMIT" <<'HOOK'
#!/bin/bash
# pre-commit: scan staged files for secrets with gitleaks

if ! command -v gitleaks &>/dev/null; then
    echo "⚠️  gitleaks not found — skipping secret scan."
    echo "   Install it: brew install gitleaks  (or see https://github.com/gitleaks/gitleaks)"
    exit 0
fi

echo "🔍 Running gitleaks on staged files..."

if gitleaks protect --staged --redact --no-banner; then
    echo "✅ No secrets detected."
    exit 0
else
    echo ""
    echo "❌ gitleaks detected potential secrets in staged files."
    echo "   Review the output above, remove the secrets, and try again."
    echo "   If this is a false positive, add a '# gitleaks:allow' comment on the line."
    exit 1
fi
HOOK

chmod +x "$PRECOMMIT"
echo "✅ pre-commit hook installed ($PRECOMMIT)"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "All hooks installed. To verify gitleaks is available:"
echo "  gitleaks version"
echo ""
echo "To install gitleaks:"
echo "  macOS:  brew install gitleaks"
echo "  Linux:  https://github.com/gitleaks/gitleaks/releases"
