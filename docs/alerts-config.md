# Alerts & Notifications Configuration

## Overview

This document defines the alert routing, prioritization, and escalation rules for the OpenClaw system.

## Alert Sources

### 1. Cron Job Failures
- **Source**: `/root/.openclaw/cron/jobs.json`
- **Trigger**: Job status = "error" OR consecutiveErrors > 0
- **Check Frequency**: Every 15 minutes

### 2. System Health
- **Source**: OpenClaw gateway status
- **Trigger**: Gateway offline, high error rates
- **Check Frequency**: Every 5 minutes

### 3. Project-Specific Alerts
- **AlphaArena**: Backend health, risk checks
- **BWTEC Kiosk**: Deployment status, errors
- **Agentwebpage**: Deployment failures

### 4. External Monitoring
- **GitHub**: Action failures, PR reviews needed
- **Vercel**: Build/deployment failures
- **Email**: Urgent unread messages

## Priority Levels

### 🔴 CRITICAL (Immediate escalation)
- System downtime
- Security incidents
- Data loss risk
- Payment/revenue impact

**Route**: Telegram + Discord + Email (if configured)
**Escalation**: Immediate

### 🟠 HIGH (Within 1 hour)
- Cron job failures (consecutiveErrors >= 2)
- Deployment failures
- API rate limits exceeded
- Model errors

**Route**: Telegram + Discord
**Escalation**: 1 hour if unacknowledged

### 🟡 MEDIUM (Within 4 hours)
- Single cron job errors
- Non-critical service degradation
- Warning thresholds

**Route**: Discord
**Escalation**: 4 hours if unacknowledged

### 🟢 LOW (Daily digest)
- Info notifications
- Successful completions
- Routine status updates

**Route**: Discord (digest)
**Escalation**: None

## Routing Rules

| Alert Type | Priority | Channels | Escalation |
|------------|----------|----------|------------|
| Cron consecutive errors | HIGH | Telegram, Discord | 1h |
| Gateway offline | CRITICAL | Telegram, Discord, Email | Immediate |
| Deployment failure | HIGH | Telegram, Discord | 1h |
| Model API errors | MEDIUM | Discord | 4h |
| Security alerts | CRITICAL | All channels | Immediate |
| Backup success | LOW | Discord (digest) | None |

## Current Alert Channels

### Telegram
- **Bot ID**: 8565262331
- **Primary channel**: Direct messages
- **Use**: Critical and High priority alerts

### Discord
- **Guild ID**: 1474583779967373423
- **Primary channel**: 1474584730543460495 (general)
- **Research channel**: 1481288633251270730 (AlphaArena)
- **Use**: All priority levels

## Alert State Tracking

Alert state is tracked in: `/root/.openclaw/workspace/memory/alert-state.json`

```json
{
  "activeAlerts": [],
  "acknowledgedAlerts": [],
  "lastCheck": "timestamp",
  "suppressedUntil": "timestamp"
}
```

## Escalation Policy

1. **First notification**: Send to primary channel
2. **Unacknowledged after 1h**: Escalate to additional channels
3. **Unacknowledged after 4h**: Mark as critical, all channels
4. **Resolution**: Update state, send resolution notice

## Suppression Rules

- Duplicate alerts within 5 minutes: Suppress
- Known maintenance windows: Suppress if tagged
- Test alerts: Mark clearly, no escalation

## Testing

Run test alerts with:
```bash
# Send test alert
echo "Test alert" | node /path/to/alert-test.js
```
