#!/usr/bin/env bash
# ==============================================================================
# build_module_zip.sh - Package Dolibarr module as installable ZIP
#
# Generates a ZIP file ready to install in Dolibarr via:
#   Admin > Modules > Deploy external module
#
# Output: dist/module_payroll_connect-<version>.zip
#
# Usage:
#   ./scripts/build_module_zip.sh            # Build with version from VERSION file
#   ./scripts/build_module_zip.sh --check    # Validate files before building
#
# The ZIP structure follows Dolibarr standards:
#   payroll_connect/
#   ├── COPYING
#   ├── admin/
#   ├── core/modules/
#   ├── core/triggers/
#   ├── core/boxes/
#   ├── img/
#   ├── langs/
#   └── lib/
# ==============================================================================

set -euo pipefail

# -- Configuration --
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$PROJECT_ROOT/dolibarr_module/VERSION"
MODULE_SRC="$PROJECT_ROOT/dolibarr_module/payroll_connect"
DIST_DIR="$PROJECT_ROOT/dist"

# -- Colors --
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# -- Functions --
usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --check    Validate module files before building"
    echo "  --help     Show this help message"
    echo ""
    echo "Output: dist/module_payroll_connect-<version>.zip"
}

get_version() {
    if [ -f "$VERSION_FILE" ]; then
        tr -d '[:space:]' < "$VERSION_FILE"
    else
        echo "0.0.0"
    fi
}

# Required files that must exist in the module
REQUIRED_FILES=(
    "core/modules/modPayrollConnect.class.php"
    "core/triggers/interface_99_modPayrollConnect_MyTrigger.class.php"
    "lib/payroll_connect.lib.php"
    "admin/setup.php"
)

# Optional but expected files
EXPECTED_FILES=(
    "COPYING"
    "admin/retry_queue.php"
    "core/boxes/box_payroll_connect_status.php"
    "langs/en_US/payroll_connect.lang"
    "langs/es_ES/payroll_connect.lang"
)

check_module() {
    echo -e "${CYAN}Validating module structure...${NC}"
    echo ""

    local errors=0

    # Check source directory
    if [ ! -d "$MODULE_SRC" ]; then
        echo -e "  ${RED}[ERROR]${NC} Module source directory not found: $MODULE_SRC"
        exit 1
    fi

    # Check required files
    echo "  Required files:"
    for file in "${REQUIRED_FILES[@]}"; do
        if [ -f "$MODULE_SRC/$file" ]; then
            echo -e "    ${GREEN}[OK]${NC}   $file"
        else
            echo -e "    ${RED}[MISSING]${NC} $file"
            errors=$((errors + 1))
        fi
    done

    # Check expected files
    echo ""
    echo "  Expected files:"
    for file in "${EXPECTED_FILES[@]}"; do
        if [ -f "$MODULE_SRC/$file" ]; then
            echo -e "    ${GREEN}[OK]${NC}   $file"
        else
            echo -e "    ${YELLOW}[WARN]${NC} $file (optional)"
        fi
    done

    # PHP syntax check
    echo ""
    echo "  PHP syntax check:"
    if command -v php > /dev/null 2>&1; then
        local php_errors=0
        while IFS= read -r -d '' phpfile; do
            if php -l "$phpfile" > /dev/null 2>&1; then
                echo -e "    ${GREEN}[OK]${NC}   $(basename "$phpfile")"
            else
                echo -e "    ${RED}[FAIL]${NC} $(basename "$phpfile")"
                php -l "$phpfile" 2>&1 | sed 's/^/           /'
                php_errors=$((php_errors + 1))
            fi
        done < <(find "$MODULE_SRC" -name "*.php" -print0)

        if [ "$php_errors" -gt 0 ]; then
            errors=$((errors + php_errors))
        fi
    else
        echo -e "    ${YELLOW}[SKIP]${NC} php not installed, skipping syntax check"
    fi

    # Version consistency check
    echo ""
    echo "  Version consistency:"
    local file_version
    file_version=$(grep -oP "\\\$this->version = '\K[^']+" "$MODULE_SRC/core/modules/modPayrollConnect.class.php" 2>/dev/null || echo "NOT_FOUND")
    local expected_version
    expected_version=$(get_version)

    if [ "$file_version" = "$expected_version" ]; then
        echo -e "    ${GREEN}[OK]${NC}   Module version ($file_version) matches VERSION file ($expected_version)"
    else
        echo -e "    ${YELLOW}[WARN]${NC} Module version ($file_version) differs from VERSION file ($expected_version)"
        echo -e "           Run ./scripts/bump_version.sh set $file_version to sync, or bump first"
    fi

    echo ""
    if [ "$errors" -gt 0 ]; then
        echo -e "${RED}Validation failed with $errors error(s)${NC}"
        exit 1
    else
        echo -e "${GREEN}Validation passed${NC}"
    fi
}

build_zip() {
    local version="$1"
    local zip_name="module_payroll_connect-${version}.zip"
    local zip_path="$DIST_DIR/$zip_name"

    # Create dist directory
    mkdir -p "$DIST_DIR"

    # Remove old ZIP with same name if exists
    [ -f "$zip_path" ] && rm "$zip_path"

    echo -e "${CYAN}Building module ZIP...${NC}"
    echo ""

    # Create ZIP from the module directory
    # -r recursive, -j junk paths off (preserve structure)
    # We cd into the parent so the ZIP root is payroll_connect/
    cd "$PROJECT_ROOT/dolibarr_module"
    zip -r "$zip_path" payroll_connect/ \
        -x "payroll_connect/.git/*" \
        -x "payroll_connect/__pycache__/*" \
        -x "payroll_connect/*.pyc" \
        -x "payroll_connect/.DS_Store" \
        -x "payroll_connect/Thumbs.db" \
        2>/dev/null

    cd "$PROJECT_ROOT"

    # Show ZIP contents
    echo ""
    echo -e "${CYAN}ZIP contents:${NC}"
    unzip -l "$zip_path" | tail -n +4 | head -n -2 | while read -r line; do
        echo "  $line"
    done

    # Show file size
    local size
    size=$(du -h "$zip_path" | cut -f1)

    echo ""
    echo -e "${GREEN}Build complete!${NC}"
    echo ""
    echo -e "  File:    ${CYAN}${zip_path}${NC}"
    echo -e "  Size:    ${size}"
    echo -e "  Version: ${version}"
    echo ""
    echo -e "  Install in Dolibarr:"
    echo -e "    Admin > Modules > Deploy external module > Upload ${zip_name}"
}

# -- Parse arguments --
DO_CHECK=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check)
            DO_CHECK=true
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

# -- Execute --
VERSION=$(get_version)

echo ""
echo -e "${CYAN}Payroll Connect Module Packager${NC}"
echo -e "Version: ${GREEN}${VERSION}${NC}"
echo ""

if [ "$DO_CHECK" = true ]; then
    check_module
    echo ""
fi

build_zip "$VERSION"
