# GENAI-A17 — Approval API & Workflow

Источник: [GenAi Risk Mitigation Action items](https://cf.avito.ru/spaces/SEC/pages/771898683/GenAi+Risk+Mitigation+Action+items)

## Суть меры

Обязательный Human-in-the-Loop перед чувствительными действиями GenAI-агентов и MCP-инструментов: любое state-changing действие (write/delete/execute/transfer) сначала уходит в очередь approvals и выполняется только после явного подтверждения уполномоченного человека.

**Зачем:** закрывает OWASP-риск **Excessive Agency** — когда вред наступает из-за того, что агент сам, без проверки, совершает high-impact действие (по причине галлюцинации, prompt injection, скомпрометированного tool). Для read-only / low-risk достаточно least privilege + allowlist + логирования; HITL включается только там, где есть необратимость или влияние на данные/деньги/публикацию.

**Связи с другими мерами в доке:**
- **A18 UI Components** — даёт UX (ApprovalModal, ActionPreview, WarningBanner), без него A17 — только бэкенд.
- **A19 Policy Engine & RACI** — решает «когда требовать approval» и «кто approver»; A17 — это исполнительный слой, A19 — правила.
- **A20 Centralized Logging** — аудит approvals пишется через тот же gateway.

В action items указано: research + реализацию предлагается отдать в AI-Lab, статус — Q3–Q4, владелец ресерча — Артём Зеленков.

## Подзадачи из меры (как разложено в Confluence)

| Приоритет | Подзадача | Что входит |
|---|---|---|
| P1 | Approval API + workflow | `request_approval()`, `approve()`, `reject()`. Поля: initiator, tool, action, object, parameters, risk_class. Интеграция с MCP-pipeline |
| P0 | Preview действия | Для каждого типа action — шаблон превью (delete → «будет удалено …, необратимо»; update → diff). Показывать approver-у, а не raw API call |
| P0 | TTL и timeouts | 10 мин для срочных, 60 мин для обычных. Timeout → reject + нотификация инициатору. Escalation при недоступности approver-а |
| P0 | Аудит | timestamp, initiator, tool, action, approver, decision, outcome — в Vault/DB. Retention ≥ 90 дней. Отчёт по HITL-метрикам (approval rate, avg time) |

## План реализации (по шагам)

### Шаг 0. Ресерч
- Бенчмарк: как HITL устроен в LangChain Permissions, Anthropic Computer Use, AWS Bedrock Agents, GitHub Copilot Workspace.
- Карта чувствительных действий в текущих MCP-инструментах Avito (пройтись по реестру разрешённых MCP, как только он будет — он сейчас блокер для A18).
- Согласовать классификацию risk_class (low/medium/high/critical) с A19. Без неё API будет принимать в себя «магические» значения.

### Шаг 1. Дизайн API и схемы запроса
- Контракт `request_approval(initiator, tool, action, object, parameters, risk_class) → approval_id`.
- `approve(approval_id, approver, reason?)`, `reject(approval_id, approver, reason)`, `get_status(approval_id)`.
- Brief-контракт + event-схема для шины (создан/решён/истёк).
- Идемпотентность: повторный `request_approval` с тем же fingerprint не плодит дубли.

### Шаг 2. MVP бэкенда
- Storage approvals (PG + индекс по статусу/TTL).
- Worker, который ставит `expired` по TTL и шлёт reject-нотификацию.
- Аудит-лог пишется синхронно с переходом статуса, маскирование ПДн через PII Reduction Module (как в A20).

### Шаг 3. Интеграция с MCP-pipeline
- В MCP-hub: декларативная отметка инструментов `requires_approval=true` + risk_class.
- Wrapper, который перехватывает вызов dangerous tool → создаёт approval → блокирует выполнение до решения.
- Fail-safe: при недоступности Approval API — действие **не выполняется** (deny-by-default).

### Шаг 4. UI и каналы доставки (вместе с A18)
- MM-бот для approvals (он уже планируется как часть A18 после реестра MCP).
- Preview-рендеринг по типам action: `delete`, `update` (diff), `transfer`, `publish`, `execute`.
- Веб-компоненты ApprovalModal/ActionPreview/WarningBanner — в общую дизайн-систему.

### Шаг 5. Policy/RACI (передача в A19)
- Матрица: action × data_class × env → {auto, hitl, deny} + кто approver.
- Escalation path: primary → backup → security on-call.
- SLA для emergency-approvals и список действий, которые эскалировать нельзя — только reject.

### Шаг 6. Observability
- Метрики: approval_rate, time_to_decision (p50/p95), timeout_rate, reject_reasons, доля автоодобрений.
- Дашборд в общем Security Dashboards (это отдельная мера в доке).
- Алерты: rejected high-risk, серия timeouts, аномалии по approver.

## План пилота

### Кандидаты на пилот
Брать не более 1–2, чтобы быстро итерировать:
- 1 «громкий» MCP с операциями записи — например, что-то меняющее данные в Confluence / Jira / Mattermost от лица бота.
- 1 внутренний агент с действиями над инфрой (deploy/rollback/feature-flag).

### Скоуп MVP пилота
- 1 risk_class — `high` (только необратимые действия).
- 1 канал approver-а — MM-бот.
- Жёсткий TTL = 30 мин, fail-safe = reject.
- Полный аудит, без эскалаций (на первой итерации).

### Метрики успеха пилота (exit criteria)
- ≥ 95% high-risk действий прошли через approval (метрика покрытия — сверять через логи MCP-hub).
- p95 time_to_decision ≤ 15 мин (иначе UX неюзабельный).
- 0 инцидентов «approve без preview» (qualitative review 20 случаев).
- Approval Fatigue check: доля approve < 60 сек после открытия preview — если зашкаливает, превью нечитабельно, надо переделывать.
- 0 случаев выполнения действия в обход API (ловится сверкой логов MCP vs approvals storage).

### Длительность пилота
4–6 недель, потом ретро + решение о масштабировании (включаем medium risk_class, добавляем второй канал, подключаем RACI из A19).

### Риски пилота, на которые смотреть отдельно
- **Approver bottleneck** — нужны бэкапы и групповые approvers.
- **«Кнопочная усталость»** — лечится UX-ревью превью (A18) и аналитикой времени между открытием и approve.
- **Out-of-band обход** — критично закрыть к MVP, иначе мера фиктивная.
