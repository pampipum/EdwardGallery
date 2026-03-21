#!/bin/bash
# manage-cron.sh - View and manage workspace cron jobs

set -e

ACTION="${1:-status}"

case "$ACTION" in
  status|list)
    echo "Current Cron Jobs"
    echo "================="
    crontab -l 2>/dev/null || echo "No crontab configured"
    echo ""
    echo "Log Files:"
    echo "----------"
    find /root/.openclaw/workspace -name "cron*.log" -type f 2>/dev/null | head -10
    find /root/workspace/projects -name "cron*.log" -type f 2>/dev/null | head -10
    ;;
  
  logs)
    PROJECT="${2:-all}"
    if [ "$PROJECT" = "all" ]; then
      echo "Recent cron logs:"
      echo "================="
      find /root/.openclaw/workspace -name "cron*.log" -type f -exec echo "--- {} ---" \; -exec tail -20 {} \; 2>/dev/null
      find /root/workspace/projects -name "cron*.log" -type f -exec echo "--- {} ---" \; -exec tail -20 {} \; 2>/dev/null
    else
      LOG_FILE=$(find /root/.openclaw/workspace /root/workspace/projects -name "cron*${PROJECT}*.log" -type f 2>/dev/null | head -1)
      if [ -n "$LOG_FILE" ]; then
        tail -50 "$LOG_FILE"
      else
        echo "No log file found for: $PROJECT"
      fi
    fi
    ;;
  
  install)
    echo "Installing cron jobs..."
    bash /root/.openclaw/workspace/scripts/setup-cron-jobs.sh
    ;;
  
  remove)
    PROJECT="${2:-}"
    if [ -z "$PROJECT" ]; then
      echo "Usage: $0 remove <project-name>"
      echo "Projects: ai-audits, scrapling-project, all"
      exit 1
    fi
    
    if [ "$PROJECT" = "all" ]; then
      crontab -r
      echo "✓ All cron jobs removed"
    else
      crontab -l | grep -v "$PROJECT" | crontab -
      echo "✓ Removed cron jobs for: $PROJECT"
    fi
    ;;
  
  test)
    PROJECT="${2:-}"
    if [ -z "$PROJECT" ]; then
      echo "Usage: $0 test <project-name>"
      echo "Projects: ai-audits, scrapling-project"
      exit 1
    fi
    
    case "$PROJECT" in
      ai-audits)
        echo "Testing AI Audits scripts..."
        cd /root/.openclaw/workspace/ai-audits
        echo "Testing lead fetch..."
        bash scripts/run-lead-fetch.sh
        echo "Testing critique email (dry-run, no recipient)..."
        bash scripts/run-critique-email.sh || true
        ;;
      scrapling-project)
        echo "Testing scrapling-project scripts..."
        cd /root/workspace/projects/scrapling-project
        echo "Testing OpenClaw job..."
        bash run_openclaw_job.sh || true
        ;;
      *)
        echo "Unknown project: $PROJECT"
        exit 1
        ;;
    esac
    ;;
  
  *)
    echo "Cron Job Manager"
    echo "================"
    echo ""
    echo "Usage: $0 <action> [options]"
    echo ""
    echo "Actions:"
    echo "  status, list    - Show current cron jobs and log files"
    echo "  logs [project]  - Show recent log output (all or specific project)"
    echo "  install         - Install workspace cron jobs"
    echo "  remove <proj>   - Remove cron jobs for a project (or 'all')"
    echo "  test <project>  - Test a project's cron scripts manually"
    echo ""
    echo "Examples:"
    echo "  $0 status"
    echo "  $0 logs ai-audits"
    echo "  $0 install"
    echo "  $0 test ai-audits"
    ;;
esac
