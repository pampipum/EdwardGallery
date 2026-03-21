# Alert Scan Report - 2026-03-19 10:50 GMT

## Summary

**Total Active Alerts: 4**
- 🔴 CRITICAL: 0
- 🟠 HIGH: 3
- 🟡 MEDIUM: 1
- 🟢 LOW: 0

## Alert Details

### HIGH Priority

#### Alert #1: Weekly Monetization Report - Timeout
- **Job ID**: `8c937039-7474-41eb-ba8b-9b1c40334b73`
- **Job Name**: Weekly Monetization & Offer Ideas Report
- **Consecutive Errors**: 2
- **Last Error**: `cron: job execution timed out`
- **Last Run**: 2026-03-17 (timestamp: 1773878400014)
- **Schedule**: Thursdays 8:00 AM AWST
- **Root Cause**: Job exceeded 420 second timeout limit
- **Recommended Fix**: 
  - Increase timeout in cron job configuration
  - Or optimize the prompt/script to complete faster
  - Consider splitting into smaller tasks

#### Alert #2: AlphaArena Weekend Open - Model Error
- **Job ID**: `d90499d2-2c95-49c6-b5c8-b383854fb3ae`
- **Job Name**: AlphaArena crypto cadence - open time (weekends)
- **Consecutive Errors**: 2
- **Last Error**: `gpt-5.3-codex-spark model not supported with ChatGPT account`
- **Last Run**: 2026-03-13 (timestamp: 1773581400029)
- **Schedule**: Weekends 9:30 AM US/Eastern
- **Root Cause**: Model configuration mismatch - using unavailable model
- **Recommended Fix**: Update job to use `modelstudio/qwen3.5-plus`

#### Alert #3: AlphaArena Weekend Pre-Close - Model Error
- **Job ID**: `253177f9-215a-4064-9328-4ba6a39d0aaa`
- **Job Name**: AlphaArena crypto cadence - pre-close time (weekends)
- **Consecutive Errors**: 2
- **Last Error**: `gpt-5.3-codex-spark model not supported with ChatGPT account`
- **Last Run**: 2026-03-13 (timestamp: 1773603900017)
- **Schedule**: Weekends 3:45 PM US/Eastern
- **Root Cause**: Model configuration mismatch - using unavailable model
- **Recommended Fix**: Update job to use `modelstudio/qwen3.5-plus`

### MEDIUM Priority

#### Alert #4: Weekly AI Automation Report - Model Error
- **Job ID**: `1704e18d-5e39-4e5b-9a47-8f853bb443c6`
- **Job Name**: Weekly AI Automation Opportunities Report
- **Consecutive Errors**: 1
- **Last Error**: `gpt-5.3-codex-spark model not supported with ChatGPT account`
- **Last Run**: 2026-03-13 (timestamp: 1773619200016)
- **Schedule**: Mondays 8:00 AM AWST
- **Root Cause**: Model configuration mismatch - using unavailable model
- **Recommended Fix**: Update job to use `modelstudio/qwen3.5-plus`

## System Status

### Cron System
- **Total Jobs**: 16
- **Jobs with Errors**: 4 (25%)
- **Healthy Jobs**: 12 (75%)

### Notification Channels
- **Discord**: Configured (Guild: 1474583779967373423)
  - Alerts channel: 1476836744694595717
  - Research channel: 1481288633251270730
  - Ops channel: 1476836742660096090
- **Telegram**: Configured (Bot: 8565262331)

## Files Created/Updated

1. `/root/.openclaw/workspace/docs/alerts-config.md` - Alert routing configuration
2. `/root/.openclaw/workspace/memory/alert-state.json` - Active alert state tracking
3. `/root/.openclaw/workspace/memory/alerts/2026-03-19-initial-scan.md` - This report

## Next Steps

1. **Immediate**: Fix model configuration in 3 cron jobs
2. **Short-term**: Investigate and fix timeout on Weekly Monetization job
3. **Ongoing**: Set up automated alert monitoring (every 15 min)
4. **Documentation**: Update HEARTBEAT.md to include alert checks

## Alert Routing Note

Subagent cannot directly send to Discord due to cross-context restrictions. Main agent should:
1. Send alert summary to Discord #alerts channel (1476836744694595717)
2. Send critical summary to Telegram if needed
