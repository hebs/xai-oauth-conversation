#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
rm -f xai_oauth_conversation.zip
zip -r xai_oauth_conversation.zip custom_components/xai_oauth_conversation \
  -x '*/__pycache__/*' '*.pyc'
echo "Built $repo_dir/xai_oauth_conversation.zip"
