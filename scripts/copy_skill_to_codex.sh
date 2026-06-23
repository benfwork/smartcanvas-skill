#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$repo_root/smart-canvas-skill"
target_dir="${HOME}/.codex/skills/smart-canvas-skill"

if [[ ! -d "$source_dir" ]]; then
  echo "Source skill directory not found: $source_dir" >&2
  exit 1
fi

mkdir -p "$(dirname "$target_dir")"
rm -rf "$target_dir"
cp -a "$source_dir" "$target_dir"

echo "Copied $source_dir -> $target_dir"
