# claude-skills

Плагіни зі skill-ами для [Claude Code](https://claude.com/claude-code).

| Плагін | Що робить |
|---|---|
| [provider-postman](plugins/provider-postman/SKILL.md) | За документацією платіжного провайдера (лінк або файл) збирає методи — оплата в режимах SMS/DMS, recurring, статус, capture/void/refund, Apple/Google Pay — пише їх опис і генерує версійну папку запитів (v1, v2, …) та environment у Postman |

## Встановлення

У Claude Code:

```
/plugin marketplace add TychynaVova/claude-skills
/plugin install provider-postman@tychynavova-skills
```

або з терміналу:

```bash
claude plugin marketplace add TychynaVova/claude-skills
claude plugin install provider-postman@tychynavova-skills
```

Оновлення: `claude plugin update provider-postman@tychynavova-skills`.

## provider-postman

Запуск: `/provider-postman <лінк на документацію провайдера та/або шлях до файлу>`
або просто попросити Claude «зроби Postman-запити для <провайдер> за цією документацією».

Що потрібно:

- `python3` (лише стандартна бібліотека);
- Postman API key — Postman → Settings → API Keys. Ключ береться зі змінної `POSTMAN_API_KEY`
  або з `./.env` (`POSTMAN_API_KEY=PMAK-…`); якщо його немає, Claude попросить;
- опційно — розширення Claude in Chrome для документації, що рендериться JS-ом.

Результат:

- `./provider-docs/<provider>/methods.md` — опис знайдених методів з лінками на документацію, зокрема як провайдер
  вмикає SMS (авторизація + списання одним запитом) і DMS (авторизація → capture / void);
- колекція `<provider>` у Postman (створюється, якщо немає) з новою папкою `vN`; запити оплати — у варіантах `(SMS)` і `(DMS)`, якщо провайдер підтримує обидва;
- environment `<PROVIDER>_V<N>_SANDBOX` — лише base URL, ключі (порожні, заповнюєш сам)
  і змінні, які запити зберігають з відповідей.

Не комітьте `.env` та ключі.

## Ліцензія

[MIT](LICENSE)
