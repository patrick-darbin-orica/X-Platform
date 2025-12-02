#!/bin/bash
# Test runner script for XStem navigation system
# Usage: ./scripts/run-tests.sh {unit|integration|hardware|all|coverage}

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the repository root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
cd "$REPO_ROOT"

# Default pytest args
PYTEST_ARGS="-v --tb=short"

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Function to run tests
run_tests() {
    local test_path=$1
    local test_name=$2

    if [ ! -d "$test_path" ]; then
        echo -e "${YELLOW}Warning: $test_path directory not found. Skipping $test_name tests.${NC}"
        return 0
    fi

    print_header "Running $test_name Tests"

    if python -m pytest "$test_path" $PYTEST_ARGS; then
        echo -e "${GREEN}✓ $test_name tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ $test_name tests failed${NC}"
        return 1
    fi
}

# Function to show usage
show_usage() {
    echo "XStem Test Runner"
    echo ""
    echo "Usage: $0 {unit|integration|hardware|all|coverage|help}"
    echo ""
    echo "Commands:"
    echo "  unit         Run unit tests (fast, no hardware required)"
    echo "  integration  Run integration tests (multiple modules, simulated hardware)"
    echo "  hardware     Run hardware tests (requires actual Amiga robot)"
    echo "  all          Run all tests (unit + integration + hardware)"
    echo "  coverage     Run all tests with coverage report"
    echo "  help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 unit                    # Run only unit tests"
    echo "  $0 all                     # Run all available tests"
    echo "  $0 coverage                # Run with coverage analysis"
    echo ""
    echo "Advanced pytest usage:"
    echo "  python -m pytest tests/unit/test_path_planner.py -v"
    echo "  python -m pytest tests/ -k test_waypoint"
    echo "  python -m pytest tests/ --lf  # Run last failed"
}

# Main script logic
case "${1:-all}" in
    unit)
        run_tests "tests/unit" "Unit"
        exit $?
        ;;

    integration)
        run_tests "tests/integration" "Integration"
        exit $?
        ;;

    hardware)
        echo -e "${YELLOW}Warning: Hardware tests require actual Amiga robot hardware!${NC}"
        read -p "Continue with hardware tests? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Hardware tests cancelled."
            exit 0
        fi
        run_tests "tests/hardware" "Hardware"
        exit $?
        ;;

    all)
        print_header "Running All Tests"

        FAILURES=0

        # Run unit tests
        if ! run_tests "tests/unit" "Unit"; then
            FAILURES=$((FAILURES + 1))
        fi

        # Run integration tests
        if ! run_tests "tests/integration" "Integration"; then
            FAILURES=$((FAILURES + 1))
        fi

        # Ask about hardware tests
        echo ""
        echo -e "${YELLOW}Hardware tests require actual Amiga robot hardware.${NC}"
        read -p "Run hardware tests? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if ! run_tests "tests/hardware" "Hardware"; then
                FAILURES=$((FAILURES + 1))
            fi
        else
            echo "Skipping hardware tests."
        fi

        # Summary
        echo ""
        print_header "Test Summary"
        if [ $FAILURES -eq 0 ]; then
            echo -e "${GREEN}✓ All tests passed!${NC}"
            exit 0
        else
            echo -e "${RED}✗ $FAILURES test suite(s) failed${NC}"
            exit 1
        fi
        ;;

    coverage)
        print_header "Running Tests with Coverage"

        # Check if pytest-cov is installed
        if ! python -c "import pytest_cov" 2>/dev/null; then
            echo -e "${YELLOW}pytest-cov not installed. Installing...${NC}"
            pip install pytest-cov
        fi

        echo "Generating coverage report..."
        python -m pytest tests/ \
            --cov=. \
            --cov-report=html \
            --cov-report=term \
            --cov-config=.coveragerc \
            $PYTEST_ARGS

        echo ""
        echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"
        echo "Open with: firefox htmlcov/index.html"
        exit $?
        ;;

    help|--help|-h)
        show_usage
        exit 0
        ;;

    *)
        echo -e "${RED}Error: Unknown command '$1'${NC}"
        echo ""
        show_usage
        exit 1
        ;;
esac
