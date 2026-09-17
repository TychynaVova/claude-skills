# claude-skills

Плагіни зі skill-ами для [Claude Code](https://claude.com/claude-code).

| Плагін | Що робить |
|---|---|
| [provider-postman](plugins/provider-postman/SKILL.md) | За документацією платіжного провайдера (лінк або файл) збирає методи — оплата в режимах SMS/DMS з 3DS, без 3DS і з власним MPI, recurring, статус, capture/void/refund, Apple/Google Pay — пише їх опис і генерує версійну папку запитів (v1, v2, …) та environment у Postman |

## Встановлення

Два кроки, **обов'язково по черзі**: спершу підключити маркетплейс, потім встановити з нього плагін.

У Claude Code:

```
/plugin marketplace add TychynaVova/claude-skills
/plugin install provider-postman@tychynavova-skills
/reload-plugins
```

або з терміналу (потім перезапустити Claude Code):

```bash
claude plugin marketplace add TychynaVova/claude-skills
claude plugin install provider-postman@tychynavova-skills
```

Перевірка: `claude plugin list` — має бути `provider-postman@tychynavova-skills`, статус `enabled`.

### Оновлення

```bash
claude plugin marketplace update tychynavova-skills
claude plugin update provider-postman@tychynavova-skills
```

Після оновлення — `/reload-plugins` або нова сесія.

### Видалення

```bash
claude plugin uninstall provider-postman@tychynavova-skills
claude plugin marketplace remove tychynavova-skills
```

### Якщо не працює

| Симптом | Причина / що робити |
|---|---|
| `Marketplace "tychynavova-skills" not found` | Не виконано перший крок — `/plugin marketplace add TychynaVova/claude-skills` |
| `Unknown command: /provider-postman` | Skill-и з плагінів викликаються з префіксом плагіна: `/provider-postman:provider-postman`. Якщо й так не знаходить — `/reload-plugins` або нова сесія |
| Skill спрацьовує двічі / конфлікт | Є ще ручна копія в `~/.claude/skills/provider-postman` — видали її, залиш плагін |
| Не клонується репозиторій | Перевір доступ до github.com (`git ls-remote https://github.com/TychynaVova/claude-skills.git`) |

## provider-postman

Запуск: `/provider-postman:provider-postman <лінк на документацію провайдера та/або шлях до файлу>`
(формат `/<плагін>:<skill>`), або просто попросити Claude
«зроби Postman-запити для <провайдер> за цією документацією: <лінк>».

Що потрібно:

- `python3` (лише стандартна бібліотека);
- Postman API key — Postman → Settings → API Keys. Ключ береться зі змінної `POSTMAN_API_KEY`
  або з `./.env` (`POSTMAN_API_KEY=PMAK-…`); якщо його немає, Claude попросить;
- опційно — розширення Claude in Chrome для документації, що рендериться JS-ом.

Результат:

- `./provider-docs/<provider>/methods.md` — опис знайдених методів з лінками на документацію, зокрема як провайдер
  вмикає SMS (авторизація + списання одним запитом) і DMS (авторизація → capture / void);
- опис режимів 3DS: 3DS провайдера (browser info, 3DS Method, challenge, завершення), без 3DS (винятки SCA,
  soft decline), external MPI (CAVV, ECI, DS transaction id…);
- колекція `<provider>` у Postman (створюється, якщо немає) з новою папкою `vN`; для кожного методу оплати —
  всі підтримувані комбінації `{3DS | non-3DS | external MPI} × {SMS | DMS}` окремими готовими запитами;
- для Apple Pay / Google Pay — окремо `Provider token` і `Decrypted data` (розшифровані мерчантом дані:
  DPAN / network token + cryptogram + ECI, Google Pay `CRYPTOGRAM_3DS` і `PAN_ONLY`); якщо така можливість
  є лише в закритій документації провайдера — запити позначаються `[Private]` із джерелом;
- environment `<PROVIDER>_V<N>_SANDBOX` — лише base URL, ключі (порожні, заповнюєш сам)
  і змінні, які запити зберігають з відповідей;
- у звіті — статистика роботи Claude (час, модель, виклики, токени, інструменти) зі `session_stats.py`.

Не комітьте `.env` та ключі.

## Ліцензія

[MIT](LICENSE)
