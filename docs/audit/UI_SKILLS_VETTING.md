# Vetting: сторонние skills для responsive / accessibility / visual-regression

Дата: 2026-07-18 · Режим: R0 (поиск + оценка) · **Ничего не установлено.** Установка стороннего skill = запуск внешнего кода → **только с решения владельца** (см. яркий блок в отчёте оркестратора).

## Принцип оценки
Skill в этой экосистеме = `SKILL.md` + часто скрипты (npm/postinstall/shell/сетевые вызовы). Риск = выполнение чужого кода в среде с доступом к репозиторию и (потенциально) к секретам. Поэтому: предпочитать **прозрачные локальные инструменты** (аудируемые npm-пакеты) вместо непрозрачных skill-обёрток; любой сторонний skill — только после fetch+аудита его скриптов и лицензии и явного разрешения.

## РЕКОМЕНДАЦИЯ (безопасный путь, установка не требуется)
Покрыть все три задачи **аудируемыми локальными инструментами**, которые я запускаю напрямую (это не «установка skill», а обычный локальный tooling):
- **Accessibility:** `axe-core` (+ опц. Lighthouse) — репутационный OSS (MPL-2.0 / Apache-2.0), прогоняется по отрендеренному DOM; закрывает P1 impeccable (aria, роли, контраст, имена).
- **Visual-regression + responsive:** **Playwright** (Apache-2.0) — я уже использую его для рендеров 1024/1280/1366; добавляю baseline-скриншоты + diff-порог + мультивьюпорт.
- **Направленные фиксы:** уже установленный **$impeccable** (`harden` a11y, `adapt`/`typeset` touch-targets/шрифты, `clarify` контракт действий, `quieter`/`polish`).
Это даёт responsive + a11y + visual-regression **без установки стороннего кода**. Рекомендую начать так.

## Шортлист сторонних skills (если владелец захочет пакет — каждый требует fetch+аудит скриптов ПЕРЕД установкой)

### Accessibility
| Skill | Что внутри | Предв. вердикт |
|---|---|---|
| `CogappLabs/claude-plugins` accessibility-pro | Playwright + axe-core, WCAG 2.1/2.2, motion/cognitive/mobile | **caution** — организация-репо, но нужен аудит install-скриптов + лицензии |
| `airowe/claude-a11y-skill` | axe-core + jsx-a11y, режимы WCAG | **caution** — проверить скрипты/лицензию |
| `snapsynapse/skill-a11y-audit` | axe-core + Lighthouse, template-sampling | **caution** — тот же аудит |
| `masuP9/a11y-specialist-skills`, `AccessLint/skills` | WCAG 2.2/APG обзор | **caution** — аудит |

### Visual-regression / responsive
| Skill | Что внутри | Предв. вердикт |
|---|---|---|
| `lackeyjb/playwright-skill` | обёртка над Playwright (пишет/исполняет автоматизацию) | **caution** — исполняет генерируемый код; лучше Playwright напрямую |
| `patricio0312rev` visual-regression-tester | Playwright diff-порог, мультибраузер, вьюпорты | **caution** — аудит скриптов |
| Playwright Interactive | 3 агента (test/visual/a11y) | **caution** — крупнее поверхность, больше аудита |

**Ни один не помечен «safe» без построчного аудита их скриптов и лицензии.** Все обёртывают те же axe-core/Playwright/Lighthouse, что я могу запускать напрямую → выгода обёртки мала, риск внешнего кода реальный.

## Вывод
1. **По умолчанию: не устанавливать сторонние skills.** Использовать axe-core + Playwright + Lighthouse напрямую + $impeccable. Достаточно для всего пакета.
2. Если владелец всё же хочет конкретный сторонний skill — назвать его, я сделаю `WebFetch` его `SKILL.md`+скриптов, проверю лицензию/postinstall/сетевые вызовы, и вынесу решение отдельным ярким блоком **до** любой установки.
3. «Анализ дизайна только после установки набора»: набор = уже доступные локальные инструменты (Playwright у меня есть; axe-core/Lighthouse — аудируемые npm), поэтому глубокий анализ можно вести без риска внешнего кода.

Источники: [airowe/claude-a11y-skill](https://github.com/airowe/claude-a11y-skill) · [CogappLabs accessibility-pro](https://github.com/CogappLabs/claude-plugins/blob/main/plugins/accessibility-pro/skills/accessibility-pro/SKILL.md) · [snapsynapse/skill-a11y-audit](https://github.com/snapsynapse/skill-a11y-audit) · [masuP9/a11y-specialist-skills](https://github.com/masuP9/a11y-specialist-skills/) · [AccessLint/skills](https://github.com/AccessLint/skills) · [lackeyjb/playwright-skill](https://github.com/lackeyjb/playwright-skill) · [visual-regression-tester](https://claudemarketplaces.com/skills/patricio0312rev/skills/visual-regression-tester)
