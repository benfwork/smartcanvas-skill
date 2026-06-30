#!/usr/bin/env bash

# copies skill from WSL to Windows for use with the Desktop Windows app

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$repo_root/smart-canvas-skill"

# update Users/{username} with your username
codex_skills_dir="${CODEX_SKILLS_DIR:-/mnt/c/Users/benf2004/.codex/skills}"
target_dir="$codex_skills_dir/smart-canvas-skill"

if [[ ! -d "$source_dir" ]]; then
  echo "Source skill directory not found: $source_dir" >&2
  exit 1
fi

mkdir -p "$(dirname "$target_dir")"
rm -rf "$target_dir"
cp -a "$source_dir" "$target_dir"

echo "Copied $source_dir -> $target_dir"
