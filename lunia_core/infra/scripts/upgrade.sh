#!/usr/bin/env bash
set -e
cd /opt/lunia_core
git pull
systemctl restart lunia_api
echo "✅ Upgraded & restarted"
