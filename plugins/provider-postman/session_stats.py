#!/usr/bin/env python3
"""Статистика використання Claude Code для звіту skill-а provider-postman.

Використання:
  python3 session_stats.py [--cwd <робоча директорія сесії>] [--transcript <шлях до .jsonl>]
                           [--marker provider-postman] [--idle-min 5]

Читає транскрипт поточної сесії (~/.claude/projects/<cwd зі слешами/крапками → '-'>/<session>.jsonl,
найсвіжіший за часом зміни) і рахує показники від ОСТАННЬОГО запуску skill-а (повідомлення користувача
з маркером) до кінця транскрипту, разом із транскриптами субагентів цієї сесії.
"""
import argparse
import collections
import glob
import json
import os
import re
from datetime import datetime


def parse_ts(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None


def transcript_for(cwd):
    slug = re.sub(r'[^A-Za-z0-9]', '-', os.path.abspath(cwd))
    files = glob.glob(os.path.expanduser(f'~/.claude/projects/{slug}/*.jsonl'))
    if not files:
        raise SystemExit(f'Транскрипт не знайдено для {cwd} (~/.claude/projects/{slug}/)')
    return max(files, key=os.path.getmtime)


def load(path):
    rows = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def user_text(row):
    content = (row.get('message') or {}).get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ' '.join(c.get('text', '') for c in content if isinstance(c, dict))
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cwd', default=os.getcwd())
    ap.add_argument('--transcript')
    ap.add_argument('--marker', default='provider-postman')
    ap.add_argument('--idle-min', type=float, default=5.0)
    args = ap.parse_args()

    path = args.transcript or transcript_for(args.cwd)
    rows = load(path)
    start = 0
    for i, r in enumerate(rows):
        if r.get('type') == 'user' and args.marker in user_text(r):
            start = i
    rows = rows[start:]
    start_ts = parse_ts(rows[0].get('timestamp')) if rows else None

    sub_dir = os.path.splitext(path)[0]
    for sub in glob.glob(os.path.join(sub_dir, 'subagents', '*.jsonl')):
        rows += [r for r in load(sub) if start_ts and parse_ts(r.get('timestamp')) and parse_ts(r['timestamp']) >= start_ts]

    usage = collections.Counter()
    models = collections.Counter()
    tools = collections.Counter()
    postman_writes = 0
    seen = set()
    stamps = []
    for r in rows:
        ts = parse_ts(r.get('timestamp'))
        if ts:
            stamps.append(ts)
        if r.get('type') != 'assistant':
            continue
        msg = r.get('message') or {}
        for c in msg.get('content') or []:
            if isinstance(c, dict) and c.get('type') == 'tool_use':
                tools[c.get('name')] += 1
                cmd = json.dumps(c.get('input', {}))
                if 'postman_builder.py' in cmd and re.search(r'\b(build|update)\b', cmd) and '--dry' not in cmd:
                    postman_writes += 1
        mid = msg.get('id')
        if mid in seen:
            continue
        seen.add(mid)
        models[msg.get('model')] += 1
        for k, v in (msg.get('usage') or {}).items():
            if isinstance(v, int):
                usage[k] += v

    stamps.sort()
    total = (stamps[-1] - stamps[0]).total_seconds() / 60 if len(stamps) > 1 else 0
    active = sum(min((b - a).total_seconds(), args.idle_min * 60)
                 for a, b in zip(stamps, stamps[1:])) / 60

    fmt = lambda n: f'{n / 1_000_000:.2f}M' if n >= 1_000_000 else f'{n / 1000:.1f}K' if n >= 1000 else str(n)
    print('| Показник | Значення |')
    print('|---|---|')
    print(f'| Час (загальний / активний*) | {total:.1f} хв / {active:.1f} хв |')
    print(f"| Модель | {', '.join(f'{m} ×{n}' for m, n in models.items() if m)} |")
    print(f'| Викликів моделі | {len(seen)} |')
    print(f"| Токени: output | {fmt(usage['output_tokens'])} |")
    print(f"| Токени: input (без кешу) | {fmt(usage['input_tokens'])} |")
    print(f"| Токени: запис у кеш | {fmt(usage['cache_creation_input_tokens'])} |")
    print(f"| Токени: читання з кешу | {fmt(usage['cache_read_input_tokens'])} |")
    print(f"| Інструменти | {', '.join(f'{k} ×{v}' for k, v in tools.most_common())} |")
    print(f'| Запусків build/update у Postman | {postman_writes} |')
    print(f'\n*Активний час — без пауз довших за {args.idle_min:g} хв (очікування відповіді користувача).')
    print(f'Джерело: {path}. Вартість у $ — команда /cost (або /usage) у Claude Code.')


if __name__ == '__main__':
    main()
