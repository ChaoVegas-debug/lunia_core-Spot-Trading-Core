#!/bin/bash
# Batch migration script for usePolledResource → usePoller
# Usage: ./migrate_widgets.sh

set -e

WIDGETS_DIR="frontend/src/components/widgets"
ADMIN_DIR="frontend/src/components/widgets/admin"

echo "🔄 Starting batch migration..."
echo "Current usePolledResource usage:"
grep -r "usePolledResource" "$WIDGETS_DIR" --include="*.tsx" -l | wc -l

# Find all files still using usePolledResource
FILES=$(grep -r "usePolledResource" "$WIDGETS_DIR" --include="*.tsx" -l)

# Note: This is a placeholder script for manual reference
# Each widget has different polling signatures and needs manual migration
# See implementation_plan.md for migration pattern

echo "Files requiring migration:"
echo "$FILES"

echo ""
echo  "✋ Manual migration required - each widget has unique polling signature"
echo "See /Users/neomind/.gemini/antigravity/brain/5a77fe4a-6cff-41cb-a2a5-c3b6f5064c42/implementation_plan.md for migration pattern"
