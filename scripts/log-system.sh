#!/bin/bash
# log-system.sh - System event logging for OpenClaw
# Logs structured JSONL events to /root/.openclaw/workspace/logs/system.log

set -e

LOG_DIR="/root/.openclaw/workspace/logs"
LOG_FILE="$LOG_DIR/system.log"
MAX_AGE_DAYS=7

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Function: log_event
# Usage: log_event <event_type> <severity> <source> <message> [context_json]
log_event() {
    local event_type="$1"
    local severity="$2"
    local source="$3"
    local message="$4"
    local context="${5:-{}}"
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local epoch=$(date +%s)
    
    # Validate event type
    case "$event_type" in
        SYSTEM_START|SYSTEM_ERROR|AGENT_ACTION|CRON_JOB|API_CALL|DEPLOY|ALERT)
            ;;
        *)
            echo "Warning: Unknown event type '$event_type', using AGENT_ACTION" >&2
            event_type="AGENT_ACTION"
            ;;
    esac
    
    # Validate severity
    case "$severity" in
        INFO|WARNING|ERROR|CRITICAL)
            ;;
        *)
            severity="INFO"
            ;;
    esac
    
    # Build JSONL record
    local json_record
    if [ -z "$context" ] || [ "$context" = "{}" ]; then
        json_record=$(jq -n \
            --arg ts "$timestamp" \
            --argjson epoch "$epoch" \
            --arg type "$event_type" \
            --arg sev "$severity" \
            --arg src "$source" \
            --arg msg "$message" \
            '{
                timestamp: $ts,
                epoch: $epoch,
                event_type: $type,
                severity: $sev,
                source: $src,
                message: $msg,
                context: {}
            }')
    else
        json_record=$(jq -n \
            --arg ts "$timestamp" \
            --argjson epoch "$epoch" \
            --arg type "$event_type" \
            --arg sev "$severity" \
            --arg src "$source" \
            --arg msg "$message" \
            --arg ctx "$context" \
            '{
                timestamp: $ts,
                epoch: $epoch,
                event_type: $type,
                severity: $sev,
                source: $src,
                message: $msg,
                context: ($ctx | try fromjson? // {})
            }')
    fi
    
    # Append compact JSONL record
    echo "$json_record" | jq -c '.' >> "$LOG_FILE"
}

# Function: rotate_logs
# Keeps only logs from the last MAX_AGE_DAYS days
rotate_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        return 0
    fi
    
    local cutoff_date=$(date -d "$MAX_AGE_DAYS days ago" +%Y-%m-%d)
    local temp_file="$LOG_FILE.tmp"
    
    # Filter out old entries (keep recent + rotate marker)
    jq -c --arg cutoff "$cutoff_date" '
        select(.timestamp >= ($cutoff + "T00:00:00Z"))
    ' "$LOG_FILE" > "$temp_file" 2>/dev/null || true
    
    if [ -s "$temp_file" ]; then
        mv "$temp_file" "$LOG_FILE"
    else
        # If all entries are old, keep file empty with rotation marker
        echo "" > "$LOG_FILE"
    fi
    
    rm -f "$temp_file"
}

# Function: get_logs
# Usage: get_logs [event_type] [severity] [hours]
get_logs() {
    local filter_type="${1:-}"
    local filter_severity="${2:-}"
    local hours="${3:-24}"
    
    local cutoff_epoch=$(date -d "$hours hours ago" +%s)
    
    if [ ! -f "$LOG_FILE" ]; then
        echo "[]" 
        return 0
    fi
    
    jq -c --argjson cutoff "$cutoff_epoch" \
          --arg type "$filter_type" \
          --arg sev "$filter_severity" '
        select((.epoch | tonumber? // 0) >= $cutoff) |
        select(if $type != "" then .event_type == $type else true end) |
        select(if $sev != "" then .severity == $sev else true end)
    ' "$LOG_FILE" 2>/dev/null || echo "[]"
}

# Function: tail_logs
# Usage: tail_logs [count]
tail_logs() {
    local count="${1:-10}"
    
    if [ ! -f "$LOG_FILE" ]; then
        return 0
    fi
    
    tail -n "$count" "$LOG_FILE" | jq -c '.' 2>/dev/null || tail -n "$count" "$LOG_FILE"
}

# Function: count_events
# Usage: count_events [hours]
count_events() {
    local hours="${1:-24}"
    local cutoff_epoch=$(date -d "$hours hours ago" +%s)
    
    if [ ! -f "$LOG_FILE" ]; then
        echo '{"total": 0}'
        return 0
    fi
    
    jq -s --argjson cutoff "$cutoff_epoch" '
        [.[] | select((.epoch | tonumber? // 0) >= $cutoff)] |
        {
            total: length,
            by_type: (group_by(.event_type) | map({key: .[0].event_type, value: length}) | from_entries),
            by_severity: (group_by(.severity) | map({key: .[0].severity, value: length}) | from_entries)
        }
    ' "$LOG_FILE" 2>/dev/null || echo '{"total": 0}'
}

# Main: Handle command-line arguments
case "${1:-log}" in
    log)
        # log_event <type> <severity> <source> <message> [context]
        if [ $# -lt 5 ]; then
            echo "Usage: $0 log <event_type> <severity> <source> <message> [context_json]"
            echo "Event types: SYSTEM_START, SYSTEM_ERROR, AGENT_ACTION, CRON_JOB, API_CALL, DEPLOY, ALERT"
            echo "Severities: INFO, WARNING, ERROR, CRITICAL"
            exit 1
        fi
        log_event "$2" "$3" "$4" "$5" "${6:-{}}"
        ;;
    
    rotate)
        rotate_logs
        echo "✓ Log rotation complete"
        ;;
    
    get)
        get_logs "$2" "$3" "${4:-24}"
        ;;
    
    tail)
        tail_logs "${2:-10}"
        ;;
    
    count)
        count_events "${2:-24}"
        ;;
    
    status)
        echo "System Log Status"
        echo "================="
        echo "Log file: $LOG_FILE"
        if [ -f "$LOG_FILE" ]; then
            size=$(wc -c < "$LOG_FILE")
            lines=$(wc -l < "$LOG_FILE")
            echo "Size: $size bytes, $lines entries"
            echo ""
            echo "Last 5 entries:"
            tail_logs 5 | jq -r '"\(.timestamp) [\(.severity)] \(.event_type): \(.message)"' 2>/dev/null || tail -5 "$LOG_FILE"
        else
            echo "Status: No log file yet"
        fi
        ;;
    
    *)
        echo "System Log Utility"
        echo "=================="
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  log <type> <sev> <src> <msg> [ctx]  - Log an event"
        echo "  rotate                              - Rotate old logs (keep $MAX_AGE_DAYS days)"
        echo "  get [type] [sev] [hours]            - Get filtered logs"
        echo "  tail [count]                        - Show last N entries"
        echo "  count [hours]                       - Count events in time window"
        echo "  status                              - Show log status"
        echo ""
        echo "Examples:"
        echo "  $0 log SYSTEM_START INFO scheduler 'System initialized'"
        echo "  $0 log SYSTEM_ERROR ERROR api 'Connection failed' '{\"retry\": 3}'"
        echo "  $0 get AGENT_ACTION INFO 1"
        echo "  $0 tail 20"
        echo "  $0 count 24"
        ;;
esac
