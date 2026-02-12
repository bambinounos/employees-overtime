#!/usr/bin/env bash
# ==============================================================================
# bump_version.sh - Version bump script for Employees Overtime project
#
# Updates the version number across all project files:
#   - VERSION (single source of truth)
#   - Dolibarr module: modPayrollConnect.class.php
#   - Dolibarr trigger: interface_99_modPayrollConnect_MyTrigger.class.php
#
# Usage:
#   ./scripts/bump_version.sh patch     # 1.1.0 -> 1.1.1
#   ./scripts/bump_version.sh minor     # 1.1.0 -> 1.2.0
#   ./scripts/bump_version.sh major     # 1.1.0 -> 2.0.0
#   ./scripts/bump_version.sh set 2.5.0 # Set to specific version
#
# Options:
#   --no-commit    Skip automatic git commit
#   --no-tag       Skip automatic git tag
#   --help         Show this help message
# ==============================================================================

set -euo pipefail

# -- Configuration --
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$PROJECT_ROOT/VERSION"

# Files to update with the new version
DOLIBARR_MODULE="$PROJECT_ROOT/dolibarr_module/payroll_connect/core/modules/modPayrollConnect.class.php"
DOLIBARR_TRIGGER="$PROJECT_ROOT/dolibarr_module/payroll_connect/core/triggers/interface_99_modPayrollConnect_MyTrigger.class.php"

# -- Defaults --
DO_COMMIT=true
DO_TAG=true

# -- Colors --
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# -- Functions --
usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  patch          Increment patch version (x.y.Z)"
    echo "  minor          Increment minor version (x.Y.0)"
    echo "  major          Increment major version (X.0.0)"
    echo "  set <version>  Set to a specific version (e.g., 2.5.0)"
    echo "  current        Show current version"
    echo ""
    echo "Options:"
    echo "  --no-commit    Do not create a git commit"
    echo "  --no-tag       Do not create a git tag"
    echo "  --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 patch                  # 1.1.0 -> 1.1.1"
    echo "  $0 minor                  # 1.1.0 -> 1.2.0"
    echo "  $0 major                  # 1.1.0 -> 2.0.0"
    echo "  $0 set 3.0.0-beta.1       # Set exact version"
    echo "  $0 patch --no-commit      # Bump without committing"
}

get_current_version() {
    if [ ! -f "$VERSION_FILE" ]; then
        echo -e "${RED}Error: VERSION file not found at $VERSION_FILE${NC}" >&2
        exit 1
    fi
    tr -d '[:space:]' < "$VERSION_FILE"
}

validate_semver() {
    local version="$1"
    if ! echo "$version" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
        echo -e "${RED}Error: Invalid version format '$version'. Expected: MAJOR.MINOR.PATCH (e.g., 1.2.3)${NC}" >&2
        exit 1
    fi
}

bump_version() {
    local current="$1"
    local bump_type="$2"

    # Extract major.minor.patch (strip any pre-release suffix for bumping)
    local base_version
    base_version=$(echo "$current" | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+')

    local major minor patch
    major=$(echo "$base_version" | cut -d. -f1)
    minor=$(echo "$base_version" | cut -d. -f2)
    patch=$(echo "$base_version" | cut -d. -f3)

    case "$bump_type" in
        patch)
            patch=$((patch + 1))
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        *)
            echo -e "${RED}Error: Unknown bump type '$bump_type'${NC}" >&2
            exit 1
            ;;
    esac

    echo "${major}.${minor}.${patch}"
}

# Extract major.minor for Dolibarr trigger (uses 2-part version)
get_short_version() {
    local version="$1"
    echo "$version" | cut -d. -f1,2
}

update_file() {
    local file="$1"
    local pattern="$2"
    local replacement="$3"
    local label="$4"

    if [ ! -f "$file" ]; then
        echo -e "  ${YELLOW}[SKIP]${NC} $label (file not found)"
        return
    fi

    if sed -i "s|${pattern}|${replacement}|g" "$file"; then
        echo -e "  ${GREEN}[OK]${NC}   $label"
    else
        echo -e "  ${RED}[FAIL]${NC} $label"
        exit 1
    fi
}

apply_version() {
    local old_version="$1"
    local new_version="$2"
    local short_new
    short_new=$(get_short_version "$new_version")

    local short_old
    short_old=$(get_short_version "$old_version")

    echo -e "${CYAN}Updating files...${NC}"

    # 1. VERSION file
    echo "$new_version" > "$VERSION_FILE"
    echo -e "  ${GREEN}[OK]${NC}   VERSION -> $new_version"

    # 2. Dolibarr module class (full semver)
    update_file "$DOLIBARR_MODULE" \
        "\$this->version = '${old_version}'" \
        "\$this->version = '${new_version}'" \
        "modPayrollConnect.class.php -> $new_version"

    # 3. Dolibarr trigger class (short version: major.minor)
    update_file "$DOLIBARR_TRIGGER" \
        "\$this->version = '${short_old}'" \
        "\$this->version = '${short_new}'" \
        "interface_99_modPayrollConnect_MyTrigger.class.php -> $short_new"
}

# -- Parse arguments --
COMMAND=""
SET_VERSION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        patch|minor|major|current)
            COMMAND="$1"
            shift
            ;;
        set)
            COMMAND="set"
            shift
            if [[ $# -eq 0 ]]; then
                echo -e "${RED}Error: 'set' requires a version argument${NC}" >&2
                exit 1
            fi
            SET_VERSION="$1"
            shift
            ;;
        --no-commit)
            DO_COMMIT=false
            shift
            ;;
        --no-tag)
            DO_TAG=false
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown argument '$1'${NC}" >&2
            usage
            exit 1
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    usage
    exit 1
fi

# -- Execute --
CURRENT_VERSION=$(get_current_version)

if [ "$COMMAND" = "current" ]; then
    echo "$CURRENT_VERSION"
    exit 0
fi

# Calculate new version
if [ "$COMMAND" = "set" ]; then
    NEW_VERSION="$SET_VERSION"
    validate_semver "$NEW_VERSION"
else
    validate_semver "$CURRENT_VERSION"
    NEW_VERSION=$(bump_version "$CURRENT_VERSION" "$COMMAND")
fi

echo ""
echo -e "${CYAN}Version bump: ${YELLOW}${CURRENT_VERSION}${NC} -> ${GREEN}${NEW_VERSION}${NC}"
echo ""

# Apply changes
apply_version "$CURRENT_VERSION" "$NEW_VERSION"

echo ""

# Git operations
if [ "$DO_COMMIT" = true ]; then
    cd "$PROJECT_ROOT"

    # Check if inside a git repo
    if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        git add VERSION
        [ -f "$DOLIBARR_MODULE" ] && git add "$DOLIBARR_MODULE"
        [ -f "$DOLIBARR_TRIGGER" ] && git add "$DOLIBARR_TRIGGER"

        git commit -m "chore: bump version to ${NEW_VERSION}"
        echo -e "${GREEN}[OK]${NC}   Git commit created"

        if [ "$DO_TAG" = true ]; then
            git tag -a "v${NEW_VERSION}" -m "Release v${NEW_VERSION}"
            echo -e "${GREEN}[OK]${NC}   Git tag v${NEW_VERSION} created"
        fi
    else
        echo -e "${YELLOW}[SKIP]${NC} Not a git repository, skipping commit/tag"
    fi
fi

echo ""
echo -e "${GREEN}Done! Version is now ${NEW_VERSION}${NC}"
