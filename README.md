# claude-skills

Маркетплейс плагінів для [Claude Code](https://claude.com/claude-code).

## Плагіни

| Плагін | Опис |
|---|---|
| [provider-postman](plugins/provider-postman/SKILL.md) | Генерація Postman-запитів, тестів і environment за документацією платіжного провайдера |

## Встановлення

```bash
claude plugin marketplace add TychynaVova/claude-skills
claude plugin install provider-postman@tychynavova-skills
```

Оновлення:

```bash
claude plugin marketplace update tychynavova-skills
claude plugin update provider-postman@tychynavova-skills
```

Видалення:

```bash
claude plugin uninstall provider-postman@tychynavova-skills
claude plugin marketplace remove tychynavova-skills
```

## provider-postman

### Виклик

```
/provider-postman:provider-postman <URL документації | шлях до файлу | інструкція>
```

### Вимоги

- Python 3 (стандартна бібліотека)
- `POSTMAN_API_KEY` у змінній середовища або в `./.env`

### Результат

- `./provider-docs/<provider>/methods.md` — опис методів API провайдера
- Колекція `<provider>` у Postman, папка `vN`:
  - оплата: `{3DS | Non-3DS | External MPI} × {SMS | DMS}`
  - recurring: токен провайдера, MIT за scheme id
  - статус, capture, void, refund
  - Apple Pay / Google Pay: токен провайдера, розшифровані дані
  - позитивні тести для кожного запиту, негативні сценарії в підпапках `Negative`
- Environment `<PROVIDER>_V<N>_SANDBOX`

### postman_builder.py

| Команда | Дія |
|---|---|
| `workspaces` | Список workspace |
| `find <provider>` | Колекції та environment провайдера |
| `tree <collection_uid>` | Структура колекції |
| `build <spec> [--dry]` | Створення папки `vN`, запитів, тестів, environment |
| `sync <spec> [--dry]` | Додавання відсутніх папок, запитів і змінних environment |
| `update <spec>` | Перезапис наявних запитів |
| `tests <spec> [--dry]` | Оновлення тестів у наявних запитах |
| `verify <spec>` | Звірка змінних запитів з environment |

Формат spec: [`spec.example.json`](plugins/provider-postman/spec.example.json).
Статистика сесії: `session_stats.py`.

## Ліцензія

[MIT](LICENSE)
