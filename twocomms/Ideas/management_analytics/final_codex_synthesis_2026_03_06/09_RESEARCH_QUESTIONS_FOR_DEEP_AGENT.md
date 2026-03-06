# 5 Questions for a Deep Research Agent

## Формат ответа, который нужен от следующего агента

По каждому вопросу агент обязан дать:
- конкретные выводы,
- 5-10 качественных источников,
- что применимо прямо сейчас,
- что рискованно,
- benchmark ranges,
- как это внедрить в CRM TwoComms без enterprise-overkill.

## 1. Какой KPI-микс лучше всего работает для small-team B2B wholesale outbound sales

Нужно исследовать:
- какие KPI реально коррелируют с paid conversion в small outbound teams,
- как балансировать `cold outreach`, `follow-up discipline`, `repeat revenue`, `portfolio retention` и `call quality`,
- какие daily и weekly нормы считаются реалистичными для B2B wholesales, а какие создают fake activity,
- как отделять KPI for coaching от KPI for compensation.

Нужен вывод в формате:
- recommended KPI stack,
- safe thresholds,
- dangerous thresholds,
- short-term vs long-term KPI layers.

## 2. Какая модель call QA и supervisor calibration лучше всего предсказывает рост конверсии

Нужно исследовать:
- scorecards в call centers и B2B sales teams,
- как часто делать calibration,
- сколько критериев должно быть в rubric,
- как связать manual QA score с compensation и coaching, не вызвав токсичность,
- какие supervisor features действительно полезны: `monitor`, `whisper`, `barge`, live assist, transcript review.

Нужен вывод в формате:
- final QA rubric recommendation,
- calibration cadence,
- QA-to-coaching policy,
- QA-to-payroll policy.

## 3. Какие identity-resolution и duplicate-management паттерны лучше всего подходят CRM с телефонией, lead parsing и ручным вводом

Нужно исследовать:
- best practices dedupe for phone/email/store-name systems,
- multi-signal identity graphs,
- ownership conflicts,
- “create new vs append existing” flows,
- how to reduce duplicate false positives without missing real duplicates.

Нужен вывод в формате:
- exact rules,
- fuzzy rules,
- review queue design,
- anti-abuse safeguards,
- migration approach for existing dirty data.

## 4. Какой reminder and escalation cadence максимизирует callback completion и не создаёт alert fatigue

Нужно исследовать:
- reminder timing,
- queue-based action design,
- escalation ladders,
- digests vs instant notifications,
- no-report policies,
- how top CRMs and contact centers handle overdue next steps.

Нужен вывод в формате:
- manager ladder,
- admin ladder,
- max safe notification volume,
- recommended channels and time windows,
- what should be immediate vs batched.

## 5. Какую IP-telephony and call analytics architecture лучше выбрать для TwoComms

Нужно исследовать:
- какие провайдеры реально подходят по API/webhooks/recordings/supervisor functions,
- что из Украины и what global alternatives matter,
- где достаточно softphone and recordings, а где нужен full contact-center stack,
- как связать telephony с CRM, QA, score, duplicate detection и portfolio ownership,
- какой phased rollout минимизирует риски.

Нужен вывод в формате:
- provider shortlist,
- must-have feature checklist,
- rollout phases,
- estimated cost bands,
- biggest technical and process risks.
