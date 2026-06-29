# 📊 Rates Board

**Дашборд курсов валют** — ЦБ РФ, Investing.com, XFeepay.

| Курс | Источник | Способ |
|:--|:--|:--|
| 🏛 USD/RUB, EUR/RUB, CNY/RUB, TRY/RUB | ЦБ РФ | XML API |
| 📈 USD/RUB, EUR/RUB, CNY/RUB, TRY/RUB | Investing.com | curl + JSON-LD |
| 🔀 EUR/USD, CNY/USD, TRY/USD | Investing.com + fallback | curl / Frankfurter API |
| 💱 CNH/USD, EUR/USD | XFeepay | REST API |

## 🚀 Архитектура

```
GitHub Actions (cron: */15 6-23 * * *)
        ↓
   update_rates.py (curl + CBR + XFeepay)
        ↓
   rates.json → commit → push
        ↓
   GitHub Pages → https://djtoljan.github.io/rates-board
        ↓
   Браузер (автообновление каждые 5 мин)
```

- **Без локального ПК** — всё в облаке
- **Доступ из любой точки** — просто открыть ссылку
- **Автообновление** — каждые 15 минут (GitHub Actions) + каждые 5 минут (браузер)

## 🖥 Дашборд

- 4 карточки источников с визуализацией
- Сводная таблица со сравнением всех курсов
- Конвертер в RUB
- Кросс-конвертер
- Спарклайны и индикаторы изменения
- Кеширование в браузере (localStorage)

## 🛠 Локальный запуск

```bash
python3 -m http.server 8080
# → http://localhost:8080
```

## 🔄 Обновление данных

Данные обновляются **автоматически** GitHub Actions каждые 15 минут.
Также можно запустить вручную: **Actions → Update Exchange Rates → Run workflow**.

## 📁 Структура

```
.github/workflows/update-rates.yml   — GitHub Actions
index.html                           — дашборд
update_rates.py                      — парсер курсов
rates.json                           — данные (генерируется)
```
