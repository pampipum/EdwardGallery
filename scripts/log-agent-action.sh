#!/bin/bash
# log-agent-action.sh - Agent action logging for OpenClaw
# Logs agent sessions, tool calls, and sub-agent spawns to system.log

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_SCRIPT="$SCRIPT_DIR/log-system.sh"

# Ensure log script exists
if [ ! -f "$LOG_SCRIPT" ]; then
    echo "Error: log-system.sh not found at $LOG_SCRIPT" >&2
    exit 1
fi

# Function: log_session_start
# Usage: log_session_start <session_id> [session_type] [metadata_json]
log_session_start() {
    local session_id="$1"
    local session_type="${2:-main}"
    local metadata="${3:-{}}"
    
    local context=$(jq -n -c \
        --arg sid "$session_id" \
        --arg stype "$session_type" \
        --arg meta "$metadata" \
        '{session_id: $sid, session_type: $stype, phase: "start", metadata: ($meta | try fromjson? // {})}')
    
    "$LOG_SCRIPT" log AGENT_ACTION INFO "agent-session" "Session started: $session_id" "$context"
}

# Function: log_session_end
# Usage: log_session_end <session_id> <duration_ms> <success> [error_details]
log_session_end() {
    local session_id="$1"
    local duration_ms="$2"
    local success="$3"  # true/false
    local error_details="${4:-}"
    
    local context=$(jq -n -c \
        --arg sid "$session_id" \
        --arg dur "$duration_ms" \
        --arg ok "$success" \
        --arg err "$error_details" \
        '{session_id: $sid, phase: "end", duration_ms: ($dur | tonumber? // 0), success: ($ok == "true"), error_details: (if $err != "" then $err else null end)}')
    
    local severity="INFO"
    if [ "$success" = "false" ]; then
        severity="ERROR"
    fi
    
    "$LOG_SCRIPT" log AGENT_ACTION "$severity" "agent-session" "Session ended: $session_id (${duration_ms}ms)" "$context"
}

# Function: log_tool_call
# Usage: log_tool_call <session_id> <tool_name> <duration_ms> <success> [error_details]
log_tool_call() {
    local session_id="$1"
    local tool_name="$2"
    local duration_ms="${3:-0}"
    local success="$4"  # true/false
    local error_details="${5:-}"
    
    local context=$(jq -n -c \
        --arg sid "$session_id" \
        --arg tool "$tool_name" \
        --arg dur "$duration_ms" \
        --arg ok "$success" \
        --arg err "$error_details" \
        '{session_id: $sid, action_type: "tool_call", tool_name: $tool, duration_ms: ($dur | tonumber? // 0), success: ($ok == "true"), error_details: (if $err != "" then $err else null end)}')
    
    local severity="INFO"
    if [ "$success" = "false" ]; then
        severity="ERROR"
    fi
    
    "$LOG_SCRIPT" log AGENT_ACTION "$severity" "tool-call" "Tool call: $tool_name" "$context"
}

# Function: log_subagent_spawn
# Usage: log_subagent_spawn <parent_session_id> <subagent_id> <task_description>
log_subagent_spawn() {
    local parent_session_id="$1"
    local subagent_id="$2"
    local task_description="$3"
    
    local context=$(jq -n \
        --arg parent "$parent_session_id" \
        --arg child "$subagent_id" \
        --arg task "$task_description" \
        '{parent_session_id: $parent, subagent_id: $child, action_type: "subagent_spawn", task: $task}')
    
    "$LOG_SCRIPT" log AGENT_ACTION INFO "subagent" "Subagent spawned: $subagent_id" "$context"
}

# Function: log_subagent_complete
# Usage: log_subagent_complete <subagent_id> <duration_ms> <success> [result_summary]
log_subagent_complete() {
    local subagent_id="$1"
    local duration_ms="$2"
    local success="$3"
    local result_summary="${4:-}"
    
    local context=$(jq -n -c \
        --arg sid "$subagent_id" \
        --arg dur "$duration_ms" \
        --arg ok "$success" \
        --arg result "$result_summary" \
        '{subagent_id: $sid, action_type: "subagent_complete", duration_ms: ($dur | tonumber? // 0), success: ($ok == "true"), result_summary: (if $result != "" then $result else null end)}')
    
    local severity="INFO"
    if [ "$success" = "false" ]; then
        severity="ERROR"
    fi
    
    "$LOG_SCRIPT" log AGENT_ACTION "$severity" "subagent" "Subagent completed: $subagent_id" "$context"
}

# Function: log_agent_error
# Usage: log_agent_error <session_id> <error_type> <error_message> [stack_trace]
log_agent_error() {
    local session_id="$1"
    local error_type="$2"
    local error_message="$3"
    local stack_trace="${4:-}"
    
    local context=$(jq -n \
        --arg sid "$session_id" \
        --arg etype "$error_type" \
        --arg emsg "$error_message" \
        --arg stack "$stack_trace" \
        '{session_id: $sid, action_type: "error", error_type: $etype, error_message: $emsg, stack_trace: (if $stack != "" then $stack else null end)}')
    
    "$LOG_SCRIPT" log SYSTEM_ERROR ERROR "agent-error" "Agent error: $error_type - $error_message" "$context"
}

# Function: get_agent_stats
# Usage: get_agent_stats [hours]
get_agent_stats() {
    local hours="${1:-24}"
    
    # Get all AGENT_ACTION events from the time window
    "$LOG_SCRIPT" get AGENT_ACTION "" "$hours" | jq -s '
        {
            total_actions: length,
            tool_calls: [.[] | select(.context.action_type == "tool_call")] | length,
            subagent_spawns: [.[] | select(.context.action_type == "subagent_spawn")] | length,
            sessions: [.[] | select(.message | contains("Session"))] | length,
            failures: [.[] | select(.severity == "ERROR")] | length,
            tools_by_name: ([.[] | select(.context.action_type == "tool_call") | .context.tool_name] | group_by(.) | map({key: .[0], value: length}) | from_entries),
            success_rate: (
                ([.[] | select(.context.success != null)] | length) as $total |
                ([.[] | select(.context.success == true or (.context.success | tostring) == "true")] | length) as $success |
                if $total > 0 then (($success / $total) * 100 | floor) else 100 end
            )
        }
    ' 2>/dev/null || echo '{"error": "No agent actions found"}'
}

# Main: Handle command-line arguments
case "${1:-help}" in
    session-start)
        log_session_start "$2" "${3:-main}" "${4:-{}}"
        ;;
    
    session-end)
        log_session_end "$2" "$3" "$4" "${5:-}"
        ;;
    
    tool-call)
        log_tool_call "$2" "$3" "$4" "$5" "${6:-}"
        ;;
    
    subagent-spawn)
        log_subagent_spawn "$2" "$3" "$4"
        ;;
    
    subagent-complete)
        log_subagent_complete "$2" "$3" "$4" "${5:-}"
        ;;
    
    error)
        log_agent_error "$2" "$3" "$4" "${5:-}"
        ;;
    
    stats)
        get_agent_stats "${2:-24}"
        ;;
    
    *)
        echo "Agent Action Logger"
        echo "==================="
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  session-start <id> [type] [meta]     - Log session start"
        echo "  session-end <id> <duration> <ok> [err] - Log session end"
        echo "  tool-call <sid> <tool> <dur> <ok> [err] - Log tool call"
        echo "  subagent-spawn <parent> <id> <task>  - Log subagent spawn"
        echo "  subagent-complete <id> <dur> <ok> [result] - Log subagent complete"
        echo "  error <sid> <type> <msg> [stack]     - Log agent error"
        echo "  stats [hours]                        - Get agent statistics"
        echo ""
        echo "Examples:"
        echo "  $0 session-start sess_123 main '{\"user\": \"alice\"}'"
        echo "  $0 tool-call sess_123 browser 1500 true"
        echo "  $0 subagent-spawn sess_123 sub_456 'Research task'"
        echo "  $0 stats 24"
        ;;
esac
