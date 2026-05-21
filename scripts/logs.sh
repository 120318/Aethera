#!/usr/bin/env bash

echo "Aethera log management"
echo "========================="

case "$1" in
    "follow"|"f")
        service=${2:-""}
        if [ -z "$service" ]; then
            echo "Following logs for all services. Press Ctrl+C to stop."
            docker compose logs -f
        else
            echo "Following logs for $service. Press Ctrl+C to stop."
            docker compose logs -f "$service"
        fi
        ;;
    "show"|"s")
        service=${2:-""}
        lines=${3:-50}
        if [ -z "$service" ]; then
            echo "Showing the latest $lines log lines for all services..."
            docker compose logs --tail="$lines"
        else
            echo "Showing the latest $lines log lines for $service..."
            docker compose logs --tail="$lines" "$service"
        fi
        ;;
    "clear"|"c")
        echo "Refusing to delete files under config/logs automatically."
        echo "config/ is treated as local persistent data; remove log files manually after backing up anything you need."
        ;;
    *)
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  follow|f [service]       Follow logs"
        echo "  show|s [service] [lines] Show recent logs; default is 50 lines"
        echo "  clear|c                  Explain why log files are not removed automatically"
        echo ""
        echo "Service names:"
        echo "  frontend          Frontend service"
        echo "  backend           Backend service" 
        echo "  sqlite-web        SQLite Web debug service"
        echo ""
        echo "Examples:"
        echo "  $0 follow            # Follow all service logs"
        echo "  $0 f frontend        # Follow frontend logs"
        echo "  $0 show backend 100  # Show the latest 100 backend log lines"
        echo "  $0 clear             # Clean local log files"
        ;;
esac
