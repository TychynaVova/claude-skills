#!/usr/bin/env bash
# Збирає архів скіла для завантаження через браузер (claude.ai → Settings → Skills → Upload skill).
# Вимоги завантажувача: SKILL.md у корені архіву, без маніфеста плагіна (.claude-plugin/).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
name="${1:-provider-postman}"
src="$root/plugins/$name"
out="$root/dist/$name-skill.zip"

[ -f "$src/SKILL.md" ] || { echo "немає $src/SKILL.md" >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
# копіюємо вміст скіла без маніфеста плагіна
(cd "$src" && tar cf - --exclude='.claude-plugin' .) | (cd "$tmp" && tar xf -)

mkdir -p "$root/dist"
rm -f "$out"
(cd "$tmp" && zip -q -r "$out" . -x '*.DS_Store')

echo "готово: ${out#"$root"/}"
unzip -l "$out"
