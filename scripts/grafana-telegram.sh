#!/usr/bin/env bash
# Enable Telegram as the Grafana alert contact point. Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from
# the environment (export them, or let docker compose pass them from the ops env file). Without both, the
# contact point stays off and alerts are only visible in Grafana.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=ops/grafana/provisioning/alerting/contactpoints.yaml
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  rm -f "$OUT"
  echo "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID kosong: contact point Telegram dimatikan."
  exit 0
fi
umask 077
# Grafana expands $TELEGRAM_* from its own environment at startup, so the token is not written to disk.
cat > "$OUT" <<'EOF'
apiVersion: 1
contactPoints:
  - orgId: 1
    name: telegram-sales-ops
    receivers:
      - uid: telegram-sales-ops
        type: telegram
        settings:
          bottoken: $TELEGRAM_BOT_TOKEN
          chatid: $TELEGRAM_CHAT_ID
          parse_mode: None
policies:
  - orgId: 1
    receiver: telegram-sales-ops
    group_by: ["alertname"]
    group_wait: 30s
    group_interval: 5m
    repeat_interval: 4h
EOF
echo "Contact point Telegram ditulis ke $OUT. Restart grafana: docker compose --profile ops restart grafana"
