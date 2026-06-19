#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."

cd "$PROJECT_DIR"

# ── Help ────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 <major|minor|patch> [changelog_message]"
    echo ""
    echo "Arguments:"
    echo "  major|minor|patch   Semver bump type"
    echo "  changelog_message   Description for CHANGELOG (optional)"
    exit 1
}

BUMP_TYPE="${1:-}"
CHANGELOG_MSG="${2:-}"

if [[ "$BUMP_TYPE" != "major" && "$BUMP_TYPE" != "minor" && "$BUMP_TYPE" != "patch" ]]; then
    usage
fi

# ── Ensure working tree is clean ────────────────────────────
if ! git diff --quiet HEAD 2>/dev/null; then
    echo "ERROR: Working tree has uncommitted changes. Commit or stash first."
    exit 1
fi

# ── Read current version from canonical source ─────────────
CURRENT_VERSION=$(cat src/_version.py | grep -oP '"\K[^"]+')

if [[ -z "$CURRENT_VERSION" ]]; then
    echo "ERROR: Could not read version from src/_version.py"
    exit 1
fi

echo "Current version: $CURRENT_VERSION"

# ── Parse semver ────────────────────────────────────────────
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
echo "New version:     $NEW_VERSION"

# ── Update src/_version.py ──────────────────────────────────
cat > src/_version.py << EOF
__version__ = "$NEW_VERSION"
EOF
echo "  ✓ src/_version.py"

# ── Update widget/tauri.conf.json ──────────────────────────
WIDGET_CONF="widget/src-tauri/tauri.conf.json"
if [[ -f "$WIDGET_CONF" ]]; then
    sed -i "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" "$WIDGET_CONF"
    echo "  ✓ $WIDGET_CONF"
else
    echo "  ⚠ $WIDGET_CONF not found, skipping"
fi

# ── Update CHANGELOG.md ─────────────────────────────────────
TODAY=$(date +%Y-%m-%d)
CHANGELOG_HEADER="## [$NEW_VERSION] — $TODAY"
CHANGELOG_FILE="CHANGELOG.md"

if [[ -f "$CHANGELOG_FILE" ]]; then
    if grep -q "^## \[$NEW_VERSION\]" "$CHANGELOG_FILE"; then
        echo "  ⚠ Version $NEW_VERSION already in CHANGELOG.md, skipping append"
    else
        if [[ -n "$CHANGELOG_MSG" ]]; then
            # Insert after the first line (# Changelog)
            sed -i "1a\\\n${CHANGELOG_HEADER}\n\n### Added\n\n- ${CHANGELOG_MSG}\n" "$CHANGELOG_FILE"
            echo "  ✓ CHANGELOG.md updated with message"
        else
            sed -i "1a\\\n${CHANGELOG_HEADER}\n" "$CHANGELOG_FILE"
            echo "  ✓ CHANGELOG.md updated (no message)"
        fi
    fi
else
    echo "  ⚠ CHANGELOG.md not found, skipping"
fi

# ── Commit and tag ──────────────────────────────────────────
git add src/_version.py "$WIDGET_CONF" "$CHANGELOG_FILE"
git commit -m "Bump version to $NEW_VERSION${CHANGELOG_MSG:+ — $CHANGELOG_MSG}"
git tag -a "v$NEW_VERSION" -m "v$NEW_VERSION${CHANGELOG_MSG:+ — $CHANGELOG_MSG}"

echo ""
echo "=== v$NEW_VERSION created ==="
echo "Run 'git push --follow-tags' to publish."
