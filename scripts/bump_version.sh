#!/usr/bin/env bash
# ==============================================================================
# bump_version.sh - Independent version manager for each component
#
# The project has TWO independent version tracks:
#
#   server  ->  VERSION  +  salary_management/__init__.py
#   module  ->  dolibarr_module/VERSION  +  PHP files
#
# Usage:
#   ./scripts/bump_version.sh server patch       # Server: 1.1.0 -> 1.1.1
#   ./scripts/bump_version.sh module minor       # Module: 1.1.0 -> 1.2.0
#   ./scripts/bump_version.sh server major       # Server: 1.1.0 -> 2.0.0
#   ./scripts/bump_version.sh module set 2.5.0   # Module: set exact version
#   ./scripts/bump_version.sh status             # Show both versions
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

# Server (Django) version files
SERVER_VERSION_FILE="$PROJECT_ROOT/VERSION"
DJANGO_INIT="$PROJECT_ROOT/salary_management/__init__.py"

# Module (Dolibarr) version files
MODULE_VERSION_FILE="$PROJECT_ROOT/dolibarr_module/VERSION"
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
BOLD='\033[1m'
NC='\033[0m'

# -- Functions --
usage() {
    echo ""
    echo -e "${BOLD}bump_version.sh${NC} - Independent version manager"
    echo ""
    echo "Usage: $0 <component> <command> [options]"
    echo ""
    echo "Components:"
    echo "  server         Django server application"
    echo "  module         Dolibarr PayrollConnect module"
    echo "  status         Show current versions of both components"
    echo ""
    echo "Commands:"
    echo "  patch          Increment patch version  (x.y.Z)  - Bug fixes"
    echo "  minor          Increment minor version  (x.Y.0)  - New features"
    echo "  major          Increment major version  (X.0.0)  - Breaking changes"
    echo "  set <version>  Set to a specific version (e.g., 2.5.0)"
    echo ""
    echo "Options:"
    echo "  --no-commit    Do not create a git commit"
    echo "  --no-tag       Do not create a git tag"
    echo "  --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 server patch              # Server: 1.1.0 -> 1.1.1"
    echo "  $0 module minor              # Module: 1.1.0 -> 1.2.0"
    echo "  $0 server major              # Server: 1.1.0 -> 2.0.0"
    echo "  $0 module set 2.0.0          # Module: set to 2.0.0"
    echo "  $0 server patch --no-tag     # Bump without git tag"
    echo "  $0 status                    # Show both versions"
    echo ""
}

read_version_file() {
    local file="$1"
    if [ ! -f "$file" ]; then
        echo -e "${RED}Error: Version file not found: $file${NC}" >&2
        exit 1
    fi
    tr -d '[:space:]' < "$file"
}

validate_semver() {
    local version="$1"
    if ! echo "$version" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
        echo -e "${RED}Error: Invalid version format '$version'. Expected: MAJOR.MINOR.PATCH (e.g., 1.2.3)${NC}" >&2
        exit 1
    fi
}

calc_bump() {
    local current="$1"
    local bump_type="$2"

    local base_version
    base_version=$(echo "$current" | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+')

    local major minor patch
    major=$(echo "$base_version" | cut -d. -f1)
    minor=$(echo "$base_version" | cut -d. -f2)
    patch=$(echo "$base_version" | cut -d. -f3)

    case "$bump_type" in
        patch) patch=$((patch + 1)) ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        major) major=$((major + 1)); minor=0; patch=0 ;;
    esac

    echo "${major}.${minor}.${patch}"
}

get_short_version() {
    echo "$1" | cut -d. -f1,2
}

update_file() {
    local file="$1"
    local pattern="$2"
    local replacement="$3"
    local label="$4"

    if [ ! -f "$file" ]; then
        echo -e "  ${YELLOW}[SKIP]${NC} $label (file not found)"
        return 1
    fi

    if sed -i "s|${pattern}|${replacement}|g" "$file"; then
        echo -e "  ${GREEN}[OK]${NC}   $label"
        return 0
    else
        echo -e "  ${RED}[FAIL]${NC} $label"
        return 1
    fi
}

read_file_version() {
    local file="$1"
    local pattern="$2"
    local label="$3"

    if [ ! -f "$file" ]; then
        echo -e "  ${YELLOW}--${NC}     $label (not found)"
        return
    fi

    local ver
    ver=$(grep -oP "$pattern" "$file" 2>/dev/null || echo "NOT_FOUND")
    if [ "$ver" = "NOT_FOUND" ]; then
        echo -e "  ${RED}??${NC}     $label (pattern not matched)"
    else
        echo -e "  ${GREEN}${ver}${NC}   $label"
    fi
}

show_status() {
    local server_ver module_ver
    server_ver=$(read_version_file "$SERVER_VERSION_FILE")
    module_ver=$(read_version_file "$MODULE_VERSION_FILE")

    echo ""
    echo -e "${BOLD}Project Versions${NC}"
    echo ""
    echo -e "${CYAN}Server (Django):${NC}"
    echo -e "  ${GREEN}${server_ver}${NC}   VERSION (source of truth)"
    read_file_version "$DJANGO_INIT" \
        "__version__ = '\K[^']+" \
        "salary_management/__init__.py"

    local django_ver
    django_ver=$(grep -oP "__version__ = '\K[^']+" "$DJANGO_INIT" 2>/dev/null || echo "")
    if [ -n "$django_ver" ] && [ "$django_ver" != "$server_ver" ]; then
        echo -e "  ${YELLOW}[DESYNC]${NC} __init__.py ($django_ver) != VERSION ($server_ver)"
    fi

    echo ""
    echo -e "${CYAN}Module (Dolibarr):${NC}"
    echo -e "  ${GREEN}${module_ver}${NC}   dolibarr_module/VERSION (source of truth)"
    read_file_version "$DOLIBARR_MODULE" \
        "\\\$this->version = '\K[^']+" \
        "modPayrollConnect.class.php"
    read_file_version "$DOLIBARR_TRIGGER" \
        "\\\$this->version = '\K[^']+" \
        "interface_99_...Trigger.class.php"

    local doli_ver
    doli_ver=$(grep -oP "\\\$this->version = '\K[^']+" "$DOLIBARR_MODULE" 2>/dev/null || echo "")
    if [ -n "$doli_ver" ] && [ "$doli_ver" != "$module_ver" ]; then
        echo -e "  ${YELLOW}[DESYNC]${NC} PHP module ($doli_ver) != VERSION ($module_ver)"
    fi

    echo ""
}

bump_server() {
    local old_version="$1"
    local new_version="$2"

    echo -e "${CYAN}Updating server files...${NC}"
    echo ""

    echo "$new_version" > "$SERVER_VERSION_FILE"
    echo -e "  ${GREEN}[OK]${NC}   VERSION -> $new_version"
    GIT_FILES=("$SERVER_VERSION_FILE")

    if update_file "$DJANGO_INIT" \
        "__version__ = '${old_version}'" \
        "__version__ = '${new_version}'" \
        "salary_management/__init__.py -> $new_version"; then
        GIT_FILES+=("$DJANGO_INIT")
    fi
}

bump_module() {
    local old_version="$1"
    local new_version="$2"
    local short_old short_new
    short_old=$(get_short_version "$old_version")
    short_new=$(get_short_version "$new_version")

    echo -e "${CYAN}Updating module files...${NC}"
    echo ""

    echo "$new_version" > "$MODULE_VERSION_FILE"
    echo -e "  ${GREEN}[OK]${NC}   dolibarr_module/VERSION -> $new_version"
    GIT_FILES=("$MODULE_VERSION_FILE")

    if update_file "$DOLIBARR_MODULE" \
        "\$this->version = '${old_version}'" \
        "\$this->version = '${new_version}'" \
        "modPayrollConnect.class.php -> $new_version"; then
        GIT_FILES+=("$DOLIBARR_MODULE")
    fi

    if update_file "$DOLIBARR_TRIGGER" \
        "\$this->version = '${short_old}'" \
        "\$this->version = '${short_new}'" \
        "interface_99_...Trigger.class.php -> $short_new"; then
        GIT_FILES+=("$DOLIBARR_TRIGGER")
    fi
}

# -- Parse arguments --
COMPONENT=""
COMMAND=""
SET_VERSION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        server|module)
            COMPONENT="$1"
            shift
            ;;
        status)
            COMPONENT="status"
            shift
            ;;
        patch|minor|major)
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

if [ -z "$COMPONENT" ]; then
    usage
    exit 1
fi

# -- Execute --
GIT_FILES=()

if [ "$COMPONENT" = "status" ]; then
    show_status
    exit 0
fi

if [ -z "$COMMAND" ]; then
    echo -e "${RED}Error: Missing command (patch, minor, major, or set)${NC}" >&2
    usage
    exit 1
fi

# Read version for the selected component
if [ "$COMPONENT" = "server" ]; then
    CURRENT_VERSION=$(read_version_file "$SERVER_VERSION_FILE")
    COMPONENT_LABEL="Server (Django)"
else
    CURRENT_VERSION=$(read_version_file "$MODULE_VERSION_FILE")
    COMPONENT_LABEL="Module (Dolibarr)"
fi

# Calculate new version
if [ "$COMMAND" = "set" ]; then
    NEW_VERSION="$SET_VERSION"
    validate_semver "$NEW_VERSION"
else
    validate_semver "$CURRENT_VERSION"
    NEW_VERSION=$(calc_bump "$CURRENT_VERSION" "$COMMAND")
fi

# Header
echo ""
echo -e "${BOLD}${COMPONENT_LABEL}${NC}"
echo -e "${CYAN}Version bump: ${YELLOW}${CURRENT_VERSION}${NC} -> ${GREEN}${NEW_VERSION}${NC}"
echo ""

# Apply changes
if [ "$COMPONENT" = "server" ]; then
    bump_server "$CURRENT_VERSION" "$NEW_VERSION"
else
    bump_module "$CURRENT_VERSION" "$NEW_VERSION"
fi

echo ""

# Git operations
if [ "$DO_COMMIT" = true ]; then
    cd "$PROJECT_ROOT"

    if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        for f in "${GIT_FILES[@]}"; do
            git add "$f"
        done

        git commit -m "chore(${COMPONENT}): bump version to ${NEW_VERSION}"
        echo -e "${GREEN}[OK]${NC}   Git commit created"

        if [ "$DO_TAG" = true ]; then
            TAG_NAME="${COMPONENT}/v${NEW_VERSION}"
            git tag -a "$TAG_NAME" -m "${COMPONENT_LABEL} v${NEW_VERSION}"
            echo -e "${GREEN}[OK]${NC}   Git tag ${TAG_NAME} created"
            echo ""
            echo -e "  ${CYAN}To push:${NC} git push origin ${TAG_NAME}"
        fi
    else
        echo -e "${YELLOW}[SKIP]${NC} Not a git repository, skipping commit/tag"
    fi
fi

echo ""
echo -e "${GREEN}Done! ${COMPONENT_LABEL} is now ${NEW_VERSION}${NC}"
echo ""
