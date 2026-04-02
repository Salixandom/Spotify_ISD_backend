#!/bin/bash

# Spotify Collab - Interactive Management CLI
# Author: Development Team
# Description: Menu-driven interface for managing the microservices stack

set -e
set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Service list - 3-service architecture
SERVICES=("auth" "core" "collaboration" "playback" "db" "traefik")
ALL_SERVICES=("auth" "core" "collaboration" "playback")

# Helper functions
print_header() {
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${BLUE}                    Spotify Collab - Management CLI${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_status() {
    local service=$1
    local status=$(docker-compose ps -q "$service" 2>/dev/null && echo "running" || echo "stopped")

    if [ "$status" = "running" ]; then
        echo -e "${GREEN}✓${NC} $service"
    else
        echo -e "${RED}✗${NC} $service"
    fi
}

check_health() {
    local service=$1
    local endpoint=$2

    response=$(curl -s -o /dev/null -w "%{http_code}" "$endpoint" 2>/dev/null || echo "000")

    if [ "$response" = "200" ]; then
        echo -e "${GREEN}✓ Healthy${NC} ($response)"
        return 0
    else
        echo -e "${RED}✗ Unhealthy${NC} ($response)"
        return 1
    fi
}

show_menu() {
    print_header
    echo -e "${BOLD}Select an action:${NC}"
    echo ""
    echo -e "  ${CYAN}1.${NC}  Show status of all services"
    echo -e "  ${CYAN}2.${NC}  Start all services"
    echo -e "  ${CYAN}3.${NC}  Stop all services"
    echo -e "  ${CYAN}4.${NC}  Restart all services"
    echo -e "  ${CYAN}5.${NC}  View logs (all services)"
    echo -e "  ${CYAN}6.${NC}  View logs (specific service)"
    echo -e "  ${CYAN}7.${NC}  Health check (all apps)"
    echo -e "  ${CYAN}8.${NC}  Health check (specific service/apps)"
    echo -e "  ${CYAN}9.${NC}  Make migrations (create migration files)"
    echo -e "  ${CYAN}10.${NC}  Show migrations (view migration status)"
    echo -e "  ${CYAN}11.${NC}  Run migrations (apply to database)"
    echo -e "  ${CYAN}12.${NC}  Create superuser"
    echo -e "  ${CYAN}13.${NC}  Access service shell"
    echo -e "  ${CYAN}14.${NC}  Rebuild service"
    echo -e "  ${CYAN}15.${NC}  Test endpoints"
    echo -e "  ${CYAN}16.${NC}  Clean restart (remove volumes)"
    echo -e "  ${CYAN}17.${NC}  Show service URLs"
    echo -e "  ${CYAN}18.${NC}  Database operations"
    echo -e "  ${CYAN}19.${NC}  Update & Restart from Git"
    echo -e "  ${CYAN}20.${NC}  Run tests (all services)"
    echo -e "  ${CYAN}21.${NC}  Run tests (specific service)"
    echo ""
    echo -ne "${BOLD}Enter choice [0-21]: ${NC}"
}

show_status() {
    print_header
    echo -e "${BOLD}Service Status:${NC}"
    echo ""

    echo -e "${YELLOW}Containers:${NC}"
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo -e "${RED}No containers running${NC}"
    echo ""

    echo -e "${YELLOW}Resource Usage:${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "No stats available"
    echo ""

    read -p "Press Enter to continue..."
}

start_services() {
    print_header
    echo -e "${BOLD}Starting all services...${NC}"
    echo ""
    docker compose up -d
    echo ""
    echo -e "${GREEN}✓ All services started${NC}"
    sleep 2
}

stop_services() {
    print_header
    echo -e "${BOLD}Stopping all services...${NC}"
    echo ""
    docker compose down
    echo ""
    echo -e "${GREEN}✓ All services stopped${NC}"
    sleep 2
}

restart_services() {
    print_header
    echo -e "${BOLD}Restarting all services...${NC}"
    echo ""
    docker compose restart
    echo ""
    echo -e "${GREEN}✓ All services restarted${NC}"
    sleep 2
}

view_logs_all() {
    print_header
    echo -e "${BOLD}Showing logs from all services (Ctrl+C to exit):${NC}"
    echo ""
    docker compose logs -f
}

view_logs_service() {
    print_header
    echo -e "${BOLD}Select service:${NC}"
    echo ""

    PS3="Select service: "
    select service in "${SERVICES[@]}" "Back to main menu"; do
        case $service in
            "Back to main menu")
                break
                ;;
            *)
                if [ -n "$service" ]; then
                    print_header
                    echo -e "${BOLD}Showing logs from $service (Ctrl+C to exit):${NC}"
                    echo ""
                    docker compose logs -f "$service"
                fi
                break
                ;;
        esac
    done
}

health_check_all() {
    print_header
    echo -e "${BOLD}Health Check - All Apps:${NC}"
    echo ""

    echo -e "${CYAN}Auth Service Apps:${NC}"
    echo -e "${YELLOW}Auth App:${NC}           $(check_health "auth" "http://localhost/api/auth/health/")"
    echo ""

    echo -e "${CYAN}Core Service Apps:${NC}"
    echo -e "${YELLOW}Playlist App:${NC}        $(check_health "playlist" "http://localhost/api/playlists/health/")"
    echo -e "${YELLOW}Track App:${NC}           $(check_health "track" "http://localhost/api/tracks/health/")"
    echo -e "${YELLOW}Search App:${NC}          $(check_health "search" "http://localhost/api/search/health/")"
    echo -e "${YELLOW}History App:${NC}         $(check_health "history" "http://localhost/api/history/health/")"
    echo ""

    echo -e "${CYAN}Collaboration Service Apps:${NC}"
    echo -e "${YELLOW}Collab App:${NC}          $(check_health "collab" "http://localhost/api/collab/health/")"
    echo -e "${YELLOW}Share App:${NC}           $(check_health "share" "http://localhost/api/share/health/")"
    echo ""

    echo -e "${CYAN}Infrastructure:${NC}"
    echo -e "${YELLOW}Traefik Dashboard:${NC}   $(check_health "traefik" "http://localhost:8080")"
    echo ""

    read -p "Press Enter to continue..."
}

health_check_service() {
    print_header
    echo -e "${BOLD}Select service to check:${NC}"
    echo ""

    select service in "${ALL_SERVICES[@]}" "Back to main menu"; do
        case $service in
            "Back to main menu")
                break
                ;;
            *)
                if [ -n "$service" ]; then
                    print_header
                    echo -e "${BOLD}Health Check: $service${NC}"
                    echo ""

                    case $service in
                        "auth")
                            check_health "auth" "http://localhost/api/auth/health/"
                            echo ""
                            curl -s http://localhost/api/auth/health/ | jq '.' 2>/dev/null || curl -s http://localhost/api/auth/health/
                            ;;
                        "core")
                            echo -e "${CYAN}Core Service Apps:${NC}"
                            echo ""
                            for app in "playlists" "tracks" "search" "history"; do
                                echo -ne "${YELLOW}$app:${NC} "
                                check_health "$app" "http://localhost/api/$app/health/"
                                curl -s "http://localhost/api/$app/health/" | jq -r '.status' 2>/dev/null || echo "unavailable"
                            done
                            echo ""
                            echo -e "${CYAN}Overall Core Service:${NC}"
                            curl -s http://localhost/api/core/health/ | jq '.' 2>/dev/null || echo "Service unavailable"
                            ;;
                        "collaboration")
                            echo -e "${CYAN}Collaboration Service Apps:${NC}"
                            echo ""
                            for app in "collab" "share"; do
                                echo -ne "${YELLOW}$app:${NC} "
                                check_health "$app" "http://localhost/api/$app/health/"
                                curl -s "http://localhost/api/$app/health/" | jq -r '.status' 2>/dev/null || echo "unavailable"
                            done
                            echo ""
                            echo -e "${CYAN}Overall Collaboration Service:${NC}"
                            curl -s http://localhost/api/collab/health/ | jq '.' 2>/dev/null || echo "Service unavailable"
                            ;;
                    esac
                    echo ""
                fi
                read -p "Press Enter to continue..."
                break
                ;;
        esac
    done
}

run_migrations() {
    print_header
    echo -e "${BOLD}Running migrations for all services...${NC}"
    echo ""

    echo -e "${CYAN}Auth service migrations:${NC}"
    docker compose exec -T auth uv run python manage.py migrate --noinput 2>&1 || echo -e "${YELLOW}No migrations or service not running${NC}"

    echo ""
    echo -e "${CYAN}Core service migrations:${NC}"
    docker compose exec -T core uv run python manage.py migrate --noinput 2>&1 || echo -e "${YELLOW}No migrations or service not running${NC}"

    echo ""
    echo -e "${CYAN}Collaboration service migrations:${NC}"
    docker compose exec -T collaboration uv run python manage.py migrate --noinput 2>&1 || echo -e "${YELLOW}No migrations or service not running${NC}"

    echo ""
    echo -e "${GREEN}✓ Migrations completed${NC}"
    sleep 2
}

show_migrations() {
    print_header
    echo -e "${BOLD}Migration Status for All Services:${NC}"
    echo ""

    echo -e "${CYAN}Auth service migrations:${NC}"
    docker compose exec -T auth uv run python manage.py showmigrations 2>&1 || echo -e "${YELLOW}Service not running or no migrations${NC}"

    echo ""
    echo -e "${CYAN}Core service migrations:${NC}"
    docker compose exec -T core uv run python manage.py showmigrations 2>&1 || echo -e "${YELLOW}Service not running or no migrations${NC}"

    echo ""
    echo -e "${CYAN}Collaboration service migrations:${NC}"
    docker compose exec -T collaboration uv run python manage.py showmigrations 2>&1 || echo -e "${YELLOW}Service not running or no migrations${NC}"

    echo ""
    read -p "Press Enter to continue..."
}

make_migrations() {
    print_header
    echo -e "${BOLD}Select service to create migrations for:${NC}"
    echo ""

    select service in "${ALL_SERVICES[@]}" "Back to main menu"; do
        case $service in
            "Back to main menu")
                break
                ;;
            *)
                if [ -n "$service" ]; then
                    print_header
                    echo -e "${BOLD}Creating migrations for $service...${NC}"
                    echo ""
                    docker compose exec -T "$service" uv run python manage.py makemigrations

                    echo ""
                    echo -e "${GREEN}✓ Migrations created for $service${NC}"
                    echo -e "${YELLOW}⚠ Review the migration files, then commit them to git${NC}"
                fi
                read -p "Press Enter to continue..."
                break
                ;;
        esac
    done
}

create_superuser() {
    print_header
    echo -e "${BOLD}Select service for superuser creation:${NC}"
    echo ""

    select service in "${ALL_SERVICES[@]}" "Back to main menu"; do
        case $service in
            "Back to main menu")
                break
                ;;
            *)
                if [ -n "$service" ]; then
                    print_header
                    echo -e "${BOLD}Creating superuser for $service${NC}"
                    echo ""
                    docker compose exec "$service" uv run python manage.py createsuperuser
                    echo ""
                    read -p "Press Enter to continue..."
                fi
                break
                ;;
        esac
    done
}

access_shell() {
    print_header
    echo -e "${BOLD}Select service to access:${NC}"
    echo ""

    select service in "${SERVICES[@]}" "Back to main menu"; do
        case $service in
            "Back to main menu")
                break
                ;;
            *)
                if [ -n "$service" ]; then
                    print_header
                    echo -e "${BOLD}Accessing shell for $service (exit to return)${NC}"
                    echo ""
                    docker compose exec "$service" bash || docker-compose exec "$service" sh
                fi
                break
                ;;
        esac
    done
}

rebuild_service() {
    print_header
    echo -e "${BOLD}Select service to rebuild:${NC}"
    echo ""

    select service in "${ALL_SERVICES[@]}" "Back to main menu"; do
        case $service in
            "Back to main menu")
                break
                ;;
            *)
                if [ -n "$service" ]; then
                    print_header
                    echo -e "${BOLD}Rebuilding $service...${NC}"
                    echo ""
                    docker compose build "$service"
                    docker compose up -d "$service"
                    echo ""
                    echo -e "${GREEN}✓ $service rebuilt and restarted${NC}"
                    sleep 2
                fi
                break
                ;;
        esac
    done
}

test_endpoints() {
    print_header
    echo -e "${BOLD}Testing API Endpoints:${NC}"
    echo ""

    echo -e "${CYAN}Testing public endpoints...${NC}"
    echo ""

    echo -n "Auth health: "
    curl -s http://localhost/api/auth/health/ | jq -r '.status' 2>/dev/null || echo "failed"

    echo -n "Core health: "
    curl -s http://localhost/api/core/health/ | jq -r '.status' 2>/dev/null || echo "failed"

    echo -n "Collab health: "
    curl -s http://localhost/api/collab/health/ | jq -r '.status' 2>/dev/null || echo "failed"

    echo ""
    echo -e "${CYAN}Testing protected endpoints (should fail)...${NC}"
    echo ""

    echo -n "Auth me (protected): "
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/auth/me/)
    echo "$response (expected 401)"

    echo ""
    read -p "Press Enter to continue..."
}

clean_restart() {
    print_header
    echo -e "${RED}${BOLD}WARNING: This will delete all data!${NC}"
    echo ""
    read -p "Are you sure? (type 'yes' to confirm): " confirm

    if [ "$confirm" = "yes" ]; then
        echo ""
        echo -e "${BOLD}Stopping and removing all containers and volumes...${NC}"
        docker compose down -v
        docker compose up -d
        echo ""
        echo -e "${GREEN}✓ Clean restart complete${NC}"
        echo -e "${YELLOW}⚠ Don't forget to run migrations!${NC}"
        sleep 3
    else
        echo ""
        echo -e "${YELLOW}Cancelled${NC}"
        sleep 1
    fi
}

show_urls() {
    print_header
    echo -e "${BOLD}Service URLs:${NC}"
    echo ""

    echo -e "${CYAN}API Endpoints by App:${NC}"
    echo "  Auth App:           http://localhost/api/auth/"
    echo "  Playlist App:       http://localhost/api/playlists/"
    echo "  Track App:          http://localhost/api/tracks/"
    echo "  Search App:         http://localhost/api/search/"
    echo "  History App:        http://localhost/api/history/"
    echo "  Collab App:         http://localhost/api/collab/"
    echo "  Share App:          http://localhost/api/share/"
    echo ""

    echo -e "${CYAN}Health Check Endpoints by App:${NC}"
    echo "  Auth:           http://localhost/api/auth/health/"
    echo "  Playlist:       http://localhost/api/playlists/health/"
    echo "  Track:          http://localhost/api/tracks/health/"
    echo "  Search:         http://localhost/api/search/health/"
    echo "  History:        http://localhost/api/history/health/"
    echo "  Collab:         http://localhost/api/collab/health/"
    echo "  Share:          http://localhost/api/share/health/"
    echo ""

    echo -e "${CYAN}Dashboards & Tools:${NC}"
    echo "  Traefik Dashboard:  http://localhost:8080"
    echo "  Database:          localhost:5432"
    echo ""

    read -p "Press Enter to continue..."
}

database_operations() {
    print_header
    echo -e "${BOLD}Database Operations:${NC}"
    echo ""
    echo -e "  ${CYAN}1.${NC}  Access database shell (psql)"
    echo -e "  ${CYAN}2.${NC}  Create database backup"
    echo -e "  ${CYAN}3.${NC}  Restore database backup"
    echo -e "  ${CYAN}4.${NC}  Reset database (DROP all tables)"
    echo -e "  ${CYAN}5.${NC}  Back to main menu"
    echo ""
    echo -ne "${BOLD}Enter choice: ${NC}"

    read -r db_choice

    case $db_choice in
        1)
            print_header
            echo -e "${BOLD}Accessing database shell...${NC}"
            echo ""
            docker compose exec db psql -U spotifyuser -d spotifydb
            ;;
        2)
            print_header
            echo -e "${BOLD}Creating database backup...${NC}"
            backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
            docker compose exec -T db pg_dump -U spotifyuser spotifydb > "$backup_file"
            echo ""
            echo -e "${GREEN}✓ Backup saved to $backup_file${NC}"
            sleep 2
            ;;
        3)
            print_header
            echo -e "${BOLD}Restore database backup${NC}"
            echo ""
            read -p "Enter backup filename: " backup_file
            if [ -f "$backup_file" ]; then
                cat "$backup_file" | docker-compose exec -T db psql -U spotifyuser -d spotifydb
                echo ""
                echo -e "${GREEN}✓ Database restored from $backup_file${NC}"
            else
                echo -e "${RED}✗ File not found: $backup_file${NC}"
            fi
            sleep 2
            ;;
        4)
            print_header
            echo -e "${RED}${BOLD}WARNING: This will delete all data!${NC}"
            echo ""
            read -p "Are you sure? (type 'yes' to confirm): " confirm
            if [ "$confirm" = "yes" ]; then
                echo ""
                docker compose exec -T db psql -U spotifyuser -d spotifydb -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
                echo -e "${GREEN}✓ Database reset${NC}"
                echo -e "${YELLOW}⚠ Run migrations to recreate tables${NC}"
            else
                echo ""
                echo -e "${YELLOW}Cancelled${NC}"
            fi
            sleep 2
            ;;
        *)
            return
            ;;
    esac
}

run_tests_all() {
    print_header
    echo -e "${BOLD}Running tests for all services...${NC}"
    echo ""

    # Create reports directory at project root (next to manage.sh)
    local report_dir
    report_dir="$(dirname "$0")/test_reports"
    mkdir -p "$report_dir"

    local timestamp
    timestamp=$(date +%Y-%m-%d_%H-%M-%S)
    local report_file="$report_dir/test_report_${timestamp}.txt"

    local overall_pass=true

    # Helper: run pytest for one service, echo to terminal AND append to report file
    _run_service_tests() {
        local svc="$1"
        local label="$2"

        echo -e "${CYAN}━━━ ${label} ━━━${NC}"
        printf '\n=== %s ===\n' "$label" >> "$report_file"

        # Capture output; tee so it also prints live
        if docker compose exec -T "$svc" uv run pytest --tb=short -v 2>&1 \
            | tee -a "$report_file"; then
            echo -e "${GREEN}✓ ${label} passed${NC}"
            printf '>>> RESULT: PASSED\n' >> "$report_file"
        else
            echo -e "${RED}✗ ${label} failed${NC}"
            printf '>>> RESULT: FAILED\n' >> "$report_file"
            overall_pass=false
        fi
        echo ""
        printf '\n' >> "$report_file"
    }

    # Write report header
    {
        echo "========================================"
        echo " Spotify ISD Backend — Test Report"
        echo " Generated: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "========================================"
        echo ""
    } > "$report_file"

    _run_service_tests "core"          "Core Service"
    _run_service_tests "collaboration" "Collaboration Service"
    _run_service_tests "auth"          "Auth Service"

    # Write report footer
    {
        echo "========================================"
        if [ "$overall_pass" = true ]; then
            echo " OVERALL: ALL TESTS PASSED"
        else
            echo " OVERALL: SOME TESTS FAILED"
        fi
        echo "========================================"
    } >> "$report_file"

    echo ""
    if [ "$overall_pass" = true ]; then
        echo -e "${GREEN}${BOLD}All tests passed ✓${NC}"
    else
        echo -e "${RED}${BOLD}Some tests failed — see output above${NC}"
    fi

    echo ""
    echo -e "${YELLOW}Report saved to:${NC} $report_file"
    read -p "Press Enter to continue..."
}

run_tests_service() {
    print_header
    echo -e "${BOLD}Select service to test:${NC}"
    echo ""

    select service in "${ALL_SERVICES[@]}" "Back to main menu"; do
        case $service in
            "Back to main menu")
                break
                ;;
            *)
                if [ -n "$service" ]; then
                    print_header
                    echo -e "${BOLD}Select test scope for $service:${NC}"
                    echo ""
                    echo -e "  ${CYAN}1.${NC}  All tests"
                    echo -e "  ${CYAN}2.${NC}  Unit tests only"
                    echo -e "  ${CYAN}3.${NC}  Integration tests only"
                    echo ""
                    echo -ne "${BOLD}Enter choice [1-3]: ${NC}"
                    read -r scope_choice

                    print_header
                    case $scope_choice in
                        1)
                            echo -e "${BOLD}Running all tests for $service...${NC}"
                            echo ""
                            docker compose exec -T "$service" uv run pytest --tb=short 2>&1 || true
                            ;;
                        2)
                            echo -e "${BOLD}Running unit tests for $service...${NC}"
                            echo ""
                            docker compose exec -T "$service" uv run pytest tests/unit/ --tb=short 2>&1 || true
                            ;;
                        3)
                            echo -e "${BOLD}Running integration tests for $service...${NC}"
                            echo ""
                            docker compose exec -T "$service" uv run pytest tests/integration/ --tb=short 2>&1 || true
                            ;;
                        *)
                            echo -e "${RED}Invalid choice${NC}"
                            ;;
                    esac
                fi
                read -p "Press Enter to continue..."
                break
                ;;
        esac
    done
}

update_restart() {
    print_header
    echo -e "${BOLD}Update & Restart from Git${NC}"
    echo ""
    echo -e "${CYAN}This will:${NC}"
    echo "  1. Pull latest code from git"
    echo "  2. Rebuild services"
    echo "  3. Restart all services"
    echo "  4. Run migrations"
    echo ""
    read -p "Continue? (y/n): " confirm

    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo ""
        echo -e "${CYAN}Pulling latest code...${NC}"
        git pull

        echo ""
        echo -e "${CYAN}Rebuilding services...${NC}"
        docker compose build

        echo ""
        echo -e "${CYAN}Restarting services...${NC}"
        docker compose down
        docker compose up -d

        echo ""
        echo -e "${CYAN}Waiting for services to start...${NC}"
        sleep 5

        echo ""
        echo -e "${CYAN}Running migrations...${NC}"
        echo -e "${CYAN}Core service:${NC}"
        docker compose exec -T core uv run python manage.py migrate --noinput 2>&1 || echo -e "${YELLOW}No migrations to apply${NC}"
        echo -e "${CYAN}Collaboration service:${NC}"
        docker compose exec -T collaboration uv run python manage.py migrate --noinput 2>&1 || echo -e "${YELLOW}No migrations to apply${NC}"

        echo ""
        echo -e "${GREEN}✓ Update complete!${NC}"
        sleep 2
    fi
}

# Main loop
main() {
    while true; do
        clear
        show_menu
        read -r choice

        case $choice in
            1) show_status ;;
            2) start_services ;;
            3) stop_services ;;
            4) restart_services ;;
            5) view_logs_all ;;
            6) view_logs_service ;;
            7) health_check_all ;;
            8) health_check_service ;;
            9) make_migrations ;;
            10) show_migrations ;;
            11) run_migrations ;;
            12) create_superuser ;;
            13) access_shell ;;
            14) rebuild_service ;;
            15) test_endpoints ;;
            16) clean_restart ;;
            17) show_urls ;;
            18) database_operations ;;
            19) update_restart ;;
            20) run_tests_all ;;
            21) run_tests_service ;;
            0)
                echo ""
                echo -e "${GREEN}Goodbye!${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo ""
                echo -e "${RED}Invalid choice. Please try again.${NC}"
                sleep 1
                ;;
        esac
    done
}

# Start the CLI
main
