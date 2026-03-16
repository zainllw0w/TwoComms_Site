# Gemini 2.5 Pro — Диаграммы архитектуры внедрения

> **Модель**: Gemini 2.5 Pro (Antigravity)
> **Дата**: 2026-03-13
> **Назначение**: Визуальная карта внедрения для финального кодекса → имплементационного файла

---

## 1. Общая архитектура системы: Текущее состояние → Целевое

```mermaid
graph TB
    subgraph CURRENT["🟢 ТЕКУЩАЯ СИСТЕМА (production)"]
        direction TB
        C_MODELS["models.py<br/>22 модели • 1160 строк"]
        C_STATS["stats_service.py<br/>KPD + Advice • 1259 строк"]
        C_VIEWS["views.py<br/>5912 строк"]
        C_SHOP["shop_views.py<br/>946 строк"]
        C_STATSV["stats_views.py<br/>222 строки"]
        C_LEAD["lead_views.py<br/>234 строки"]
        C_PARSE["parsing_views.py<br/>381 строка"]
        C_CONST["constants.py<br/>POINTS table • 24 строки"]
        C_ADMIN["admin.py<br/>6 моделей • 78 строк"]
        C_CMD["commands/<br/>notify_test_shops.py"]
        C_TPLS["templates/<br/>17 HTML файлов"]
        C_URLS["urls.py<br/>75 URL patterns"]
    end

    subgraph TARGET["🔵 ЦЕЛЕВАЯ СИСТЕМА (после внедрения)"]
        direction TB
        T_SCORE["services/score_service.py<br/>EWR + MOSAIC"]
        T_TRUST["services/trust_service.py<br/>Trust production/diagnostic"]
        T_CHURN["services/churn_service.py<br/>Weibull + portfolio"]
        T_DEDUP["services/dedupe_service.py<br/>Normalization + matching"]
        T_PAY["services/payroll_service.py<br/>Commission + soft-floor + SPIFF"]
        T_SNAP["services/snapshot_service.py<br/>Nightly orchestration"]
        T_FORE["services/forecast_service.py<br/>Pipeline + economics"]
        T_ADV["services/advice_service.py<br/>Enhanced tips"]
        T_MODELS["models.py EXTENDED<br/>+6 новых моделей"]
        T_CMDS["commands/<br/>+4 новые команды"]
        T_TPLS2["templates/<br/>+8 новых компонентов"]
    end

    CURRENT -->|"Phase 0-4<br/>Постепенная<br/>трансформация"| TARGET

    style CURRENT fill:#1a1a2e,stroke:#16213e,color:#e94560
    style TARGET fill:#0f3460,stroke:#533483,color:#e94560
```

---

## 2. Фазовая модель внедрения

```mermaid
gantt
    title Фазы внедрения Management Analytics
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Phase 0: Подготовка
    Fix xml_connected drift         :crit, p0a, 2026-03-20, 1d
    Doc-code parity test            :p0b, after p0a, 1d
    SERVICE_CONTRACTS.md            :p0c, after p0a, 2d
    TESTING_STRATEGY.md             :p0d, after p0a, 2d

    section Phase 1: Фундамент
    ComponentReadiness model        :crit, p1a, after p0d, 1d
    NightlyScoreSnapshot model      :crit, p1b, after p1a, 1d
    CommandRunLog model              :p1c, after p1a, 1d
    ManagementStatsConfig extend    :p1d, after p1a, 1d
    Seed defaults command           :p1e, after p1b, 1d

    section Phase 2: Score Engine
    compute_ewr service             :crit, p2a, after p1e, 3d
    compute_mosaic SHADOW           :crit, p2b, after p2a, 3d
    compute_trust_production        :p2c, after p2a, 2d
    compute_score_confidence        :p2d, after p2c, 1d
    compute_nightly_scores cmd      :crit, p2e, after p2b, 2d
    extend get_stats_payload        :p2f, after p2e, 2d

    section Phase 3: UI + Transition
    Shadow MOSAIC card in stats     :p3a, after p2f, 2d
    Radar chart component           :p3b, after p3a, 2d
    Salary simulator                :p3c, after p3b, 2d
    Rescue top-5 widget             :p3d, after p3c, 1d
    Enhanced advice                 :p3e, after p3a, 2d
    Admin readiness surface         :p3f, after p3a, 2d

    section Phase 4: Payroll + Safety
    Payroll service                 :crit, p4a, after p3d, 3d
    Soft-floor + SPIFF              :p4b, after p4a, 2d
    Appeal system                   :p4c, after p4a, 2d
    Freeze/Red Card                 :p4d, after p4c, 1d
    Admin economics                 :p4e, after p4b, 2d

    section Phase 5: Hardening
    Dedupe service                  :p5a, after p4e, 3d
    Churn Weibull service           :p5b, after p4e, 2d
    Portfolio health                :p5c, after p5b, 1d
    KPD→MOSAIC activation          :milestone, p5d, after p5c, 0d
```

---

## 3. Модельная диаграмма: Существующие + Новые модели

```mermaid
erDiagram
    User ||--o{ Client : "owner"
    User ||--o{ Shop : "created_by / managed_by"
    User ||--o{ ManagementLead : "added_by / processed_by"
    User ||--o{ Report : "owner"
    User ||--o{ ManagementDailyActivity : "user"
    User ||--o{ ManagerCommissionAccrual : "owner"
    User ||--o{ ManagerPayoutRequest : "owner"
    User ||--o{ ClientFollowUp : "owner"
    User ||--o{ ManagementContract : "created_by"

    Client ||--o{ ClientFollowUp : "client"
    Client ||--o{ Report : "via owner"
    
    Shop ||--o{ ShopPhone : "shop"
    Shop ||--o{ ShopShipment : "shop"
    Shop ||--o{ ShopCommunication : "shop"
    Shop ||--o{ ShopInventoryMovement : "shop"

    ManagementLead }o--|| LeadParsingJob : "parser_job"
    ManagementLead ||--o| Client : "converted_client"

    ManagerCommissionAccrual }o--|| WholesaleInvoice : "invoice"
    ShopShipment }o--o| WholesaleInvoice : "wholesale_invoice"

    ManagementStatsConfig ||--|| ManagementStatsConfig : "singleton pk=1"

    Client {
        int id PK
        string shop_name
        string phone
        string phone_normalized
        string source
        string call_result
        int points_override
        FK owner
        datetime created_at
    }

    Shop {
        int id PK
        string name
        string shop_type
        FK created_by
        FK managed_by
        date test_connected_at
        int test_period_days
        datetime next_contact_at
    }

    NightlyScoreSnapshot {
        int id PK
        FK manager
        date snapshot_date
        float mosaic_score
        float ewr_score
        json axes_breakdown
        json raw_data
        string formula_version
        string defaults_version
        float score_confidence
        string job_run_id
        datetime computed_at
    }

    ComponentReadiness {
        int id PK
        string component
        string status
        datetime activated_at
        string reason
    }

    CommandRunLog {
        int id PK
        string command_name
        datetime started_at
        datetime finished_at
        string status
        int rows_processed
        int warnings_count
        text traceback_excerpt
    }

    ScoreAppeal {
        int id PK
        FK manager
        string appeal_type
        string status
        text reason
        text resolution
        FK resolved_by
        datetime created_at
    }

    CallRecord {
        int id PK
        FK client
        FK owner
        string source
        datetime started_at
        int duration_seconds
        string direction
        string outcome
        string provider_call_id
        json raw_payload
    }
```

---

## 4. Score Pipeline: KPD → MOSAIC transition

```mermaid
flowchart TD
    subgraph CURRENT_KPD["🟢 Текущий KPD Pipeline"]
        direction TB
        KE["Effort<br/>active_seconds^0.6 + points^0.55"]
        KQ["Quality<br/>(success_weighted+1)/(processed+5) × 2"]
        KO["Ops<br/>CP_sent + shops_created + invoices"]
        KP["Penalty<br/>missed_FU×0.8 + late_reports×0.25 + missing_reports×0.5"]
        KPD_FINAL["KPD = (E+Q+O) × (1-P)"]
        KE --> KPD_FINAL
        KQ --> KPD_FINAL
        KO --> KPD_FINAL
        KP --> KPD_FINAL
    end

    subgraph NEW_MOSAIC["🔵 Новый MOSAIC Pipeline"]
        direction TB
        M1["1. compute_raw_axes<br/>Result, SF, Process, FU, DQ, VC"]
        M2["2. apply_readiness_filter<br/>ACTIVE / SHADOW / DORMANT"]
        M3["3. compute_trust_production<br/>trust ∈ [0.85, 1.05]"]
        M4["4. apply_gates<br/>evidence → gate cap"]
        M5["5. compute_weighted_score<br/>Σ(axis × weight)"]
        M6["6. apply_trust<br/>score × trust"]
        M7["7. apply_dampener<br/>EWMA smoothing"]
        M8["8. apply_onboarding_floor<br/>max(dampened, floor)"]
        M9["9. compute_confidence<br/>HIGH / MEDIUM / LOW"]
        M1 --> M2 --> M3 --> M4 --> M5 --> M6 --> M7 --> M8 --> M9
    end

    subgraph TRANSITION["🟡 Transition Period"]
        direction TB
        T1["Shadow: KPD = production, MOSAIC = diagnostic"]
        T2["Parallel: Оба видимы, KPD = primary"]
        T3["Flip: MOSAIC = primary, KPD = secondary"]
        T4["Full: MOSAIC = production, KPD = archived"]
        T1 --> T2 --> T3 --> T4
    end

    CURRENT_KPD -.->|"8+ weeks shadow"| TRANSITION
    TRANSITION -.->|"Activation gate"| NEW_MOSAIC

    style CURRENT_KPD fill:#1b4332,stroke:#2d6a4f,color:#d8f3dc
    style NEW_MOSAIC fill:#0d1b2a,stroke:#1b3a4b,color:#a9d6e5
    style TRANSITION fill:#3c1518,stroke:#69140e,color:#f2b5d4
```

---

## 5. Data Flow: Nightly Score Computation

```mermaid
flowchart LR
    subgraph INPUT["📥 Input Data"]
        DB_CLIENT["Client<br/>call_result, source,<br/>created_at, owner"]
        DB_SHOP["Shop<br/>shipments, comms,<br/>stale/overdue"]
        DB_FU["ClientFollowUp<br/>missed, done,<br/>rescheduled"]
        DB_ACT["DailyActivity<br/>active_seconds"]
        DB_REPORT["Report<br/>created_at<br/>(late/on_time)"]
        DB_CP["CommercialOffer<br/>EmailLog<br/>sent/failed"]
        DB_INVOICE["WholesaleInvoice<br/>total_amount,<br/>is_approved"]
    end

    subgraph COMPUTE["⚙️ Compute Layer"]
        COMP_EWR["compute_ewr()"]
        COMP_AXES["compute_raw_axes()"]
        COMP_TRUST["compute_trust()"]
        COMP_MOSAIC["compute_mosaic()"]
        COMP_KPD["compute_kpd()<br/>LEGACY"]
        COMP_CONF["compute_confidence()"]
        COMP_CHURN["compute_churn_weibull()"]
        COMP_ADVICE["generate_advice()"]
    end

    subgraph OUTPUT["📤 Output"]
        SNAP["NightlyScoreSnapshot<br/>mosaic, ewr, trust,<br/>axes, confidence"]
        LOG["CommandRunLog<br/>status, duration,<br/>warnings"]
        PAYLOAD["stats_payload<br/>→ stats.html"]
    end

    DB_CLIENT --> COMP_EWR
    DB_CLIENT --> COMP_AXES
    DB_SHOP --> COMP_AXES
    DB_FU --> COMP_AXES
    DB_ACT --> COMP_KPD
    DB_REPORT --> COMP_KPD
    DB_CP --> COMP_KPD
    DB_INVOICE --> COMP_EWR

    COMP_EWR --> COMP_AXES
    COMP_AXES --> COMP_TRUST
    COMP_TRUST --> COMP_MOSAIC
    COMP_MOSAIC --> SNAP
    COMP_MOSAIC --> COMP_CONF
    COMP_CONF --> SNAP
    COMP_CHURN --> SNAP

    COMP_KPD --> PAYLOAD
    COMP_MOSAIC --> PAYLOAD
    COMP_ADVICE --> PAYLOAD
    SNAP --> PAYLOAD

    style INPUT fill:#2b2d42,stroke:#8d99ae,color:#edf2f4
    style COMPUTE fill:#14213d,stroke:#fca311,color:#e5e5e5
    style OUTPUT fill:#023047,stroke:#219ebc,color:#8ecae6
```

---

## 6. File Decomposition: Текущая → Целевая структура

```mermaid
graph LR
    subgraph BEFORE["📁 ДО"]
        B_MODELS["models.py<br/>1160 строк / 22 модели"]
        B_STATS["stats_service.py<br/>1259 строк / KPD+advice"]
        B_VIEWS["views.py<br/>5912 строк / god-file"]
        B_CONST["constants.py<br/>24 строки"]
        B_ADMIN["admin.py<br/>78 строк / 6 моделей"]
        B_CMD["commands/<br/>1 файл"]
    end

    subgraph AFTER["📁 ПОСЛЕ"]
        A_MODELS["models.py EXTENDED<br/>+ 6 новых моделей<br/>~1500 строк"]
        
        A_SVC1["services/score_service.py"]
        A_SVC2["services/trust_service.py"]
        A_SVC3["services/churn_service.py"]
        A_SVC4["services/dedupe_service.py"]
        A_SVC5["services/payroll_service.py"]
        A_SVC6["services/snapshot_service.py"]
        A_SVC7["services/forecast_service.py"]
        A_SVC8["services/advice_service.py"]
        
        A_VIEWS["views.py<br/>СОХРАНИТЬ<br/>5912 строк"]
        A_STATSV["stats_views.py<br/>РАСШИРИТЬ"]
        
        A_CONST["constants.py<br/>ИСПРАВИТЬ xml_connected<br/>+ добавить MOSAIC consts"]
        
        A_ADMIN["admin.py<br/>+ 6 новых моделей"]
        
        A_CMD1["commands/compute_nightly_scores.py"]
        A_CMD2["commands/check_duplicate_queue.py"]
        A_CMD3["commands/send_management_reminders.py"]
        A_CMD4["commands/process_telephony_webhooks.py"]
        A_CMD5["commands/notify_test_shops.py<br/>KEEP"]
        
        A_TESTS["tests/<br/>15+ test modules"]
    end

    B_MODELS -->|"EXTEND"| A_MODELS
    B_STATS -->|"KEEP + services/"| A_SVC1
    B_STATS -.->|"extract"| A_SVC2
    B_STATS -.->|"extract"| A_SVC3
    B_STATS -.->|"extract"| A_SVC8
    B_VIEWS -->|"KEEP AS IS"| A_VIEWS
    B_CONST -->|"FIX + EXTEND"| A_CONST
    B_ADMIN -->|"EXTEND"| A_ADMIN
    B_CMD -->|"ADD NEW"| A_CMD1

    style BEFORE fill:#2d0000,stroke:#8b0000,color:#ff6961
    style AFTER fill:#001a00,stroke:#006400,color:#90ee90
```

---

## 7. Telegram Integration Flow

```mermaid
sequenceDiagram
    participant M as Manager
    participant APP as Django App
    participant TG as Telegram Bot
    participant ADMIN as Admin (TG)

    Note over M,ADMIN: === Текущий Payout Flow ===
    M->>APP: POST /payouts/api/request/
    APP->>APP: Create ManagerPayoutRequest(status=processing)
    APP->>TG: sendMessage(admin_chat_id, "Запит на виплату...")
    APP->>APP: Save admin_tg_chat_id + admin_tg_message_id
    
    ADMIN->>TG: Approve/Reject button
    TG->>APP: Webhook callback
    APP->>APP: Update PayoutRequest status
    APP->>TG: sendMessage(manager_chat_id, "Виплата схвалена")

    Note over M,ADMIN: === Новый MOSAIC Alert Flow ===
    APP->>APP: compute_nightly_scores (cron 2:00)
    APP->>APP: Detect anomaly (score drop >20pts)
    APP->>TG: sendMessage(admin_chat_ids, "⚠️ Score anomaly...")
    ADMIN->>TG: Review / Freeze / Ignore
    TG->>APP: Webhook callback
    APP->>APP: Log decision in AuditLog

    Note over M,ADMIN: === Новый Appeal Flow ===
    M->>APP: POST /appeals/api/submit/
    APP->>APP: Create ScoreAppeal(status=pending)
    APP->>TG: sendMessage(admin_chat_id, "📋 Апеляція...")
    ADMIN->>TG: Accept / Reject + reason
    TG->>APP: Webhook callback
    APP->>APP: Update appeal, recalc if needed
    APP->>TG: sendMessage(manager_chat_id, "Результат апеляції...")
```

---

## 8. Client Lifecycle: Full Journey (Lead → Client → Shop → Revenue)

```mermaid
flowchart TD
    subgraph LEAD_STAGE["🔍 Lead Stage"]
        L1["Google Maps Parser<br/>(LeadParsingJob)"]
        L2["Manual Entry"]
        L3["LeadParsingResult<br/>added/duplicate/no_phone"]
        L1 --> L3
        L2 --> L4["ManagementLead<br/>status: moderation"]
        L3 -->|"added"| L4
    end

    subgraph MODERATION["✅ Moderation"]
        L4 -->|"approve"| L5["ManagementLead<br/>status: base"]
        L4 -->|"reject"| L6["ManagementLead<br/>status: rejected"]
    end

    subgraph CLIENT_STAGE["📞 Client Stage"]
        L5 -->|"convert"| C1["Client<br/>call_result: no_answer"]
        C1 -->|"call"| C2["Client<br/>call_result: thinking/sent_email/etc"]
        C2 -->|"follow-up"| C3["ClientFollowUp<br/>open → done/missed"]
        C2 -->|"order"| C4["Client<br/>call_result: order/test_batch"]
    end

    subgraph SHOP_STAGE["🏪 Shop Stage"]
        C4 -->|"test"| S1["Shop<br/>type: test"]
        C4 -->|"full order"| S2["Shop<br/>type: full"]
        S1 -->|"convert"| S2
        S1 -->|"expire"| S3["overdue test<br/>(stats tracking)"]
        S2 --> S4["ShopShipment<br/>deliveries"]
        S2 --> S5["ShopCommunication<br/>retention touches"]
        S2 --> S6["ShopInventoryMovement<br/>sales tracking"]
    end

    subgraph REVENUE["💰 Revenue Stage"]
        S4 --> R1["WholesaleInvoice<br/>(orders app)"]
        R1 --> R2["ManagerCommissionAccrual<br/>frozen_until"]
        R2 -->|"unfreeze"| R3["ManagerPayoutRequest<br/>processing → paid"]
    end

    subgraph ANALYTICS["📊 Analytics Layer"]
        C1 -.-> A1["KPD Score"]
        C3 -.-> A1
        S2 -.-> A2["Shop Health"]
        R1 -.-> A3["Revenue Attribution"]
        A1 -.-> A4["MOSAIC Score<br/>(NEW - SHADOW)"]
        A2 -.-> A4
        A3 -.-> A4
        A4 -.-> A5["NightlyScoreSnapshot<br/>(NEW)"]
    end

    style LEAD_STAGE fill:#1a1a2e,stroke:#e94560,color:#eaeaea
    style MODERATION fill:#16213e,stroke:#0f3460,color:#eaeaea
    style CLIENT_STAGE fill:#0f3460,stroke:#533483,color:#eaeaea
    style SHOP_STAGE fill:#533483,stroke:#e94560,color:#eaeaea
    style REVENUE fill:#2d6a4f,stroke:#40916c,color:#eaeaea
    style ANALYTICS fill:#14213d,stroke:#fca311,color:#eaeaea
```

---

## 9. MOSAIC Score Axes: Weight Distribution

```mermaid
pie title MOSAIC Axes Weights (Production)
    "Result (0.40)" : 40
    "SourceFairness (0.15)" : 15
    "Process (0.15)" : 15
    "FollowUp (0.15)" : 15
    "DataQuality (0.10)" : 10
    "VerifiedComm (0.05)" : 5
```

---

## 10. Migration Dependency Chain

```mermaid
flowchart TD
    subgraph PHASE_0["Phase 0: Prep"]
        FIX["Fix constants.py<br/>xml_connected: 15→?"]
        TEST_PARITY["Add doc-code<br/>parity test"]
        FIX --> TEST_PARITY
    end

    subgraph PHASE_1["Phase 1: Foundation Models"]
        M_CR["0020: ComponentReadiness<br/>model + seed"]
        M_NSS["0021: NightlyScoreSnapshot<br/>model"]
        M_CRL["0022: CommandRunLog<br/>model"]
        M_CFG["0023: ManagementStatsConfig<br/>add mosaic_weights,<br/>defaults_version"]
        M_CR --> M_NSS
        M_CR --> M_CRL
        M_CR --> M_CFG
    end

    subgraph PHASE_2["Phase 2: Score Models"]
        M_DL["0024: ManagerDayStatus<br/>capacity_factor,<br/>force_majeure"]
        M_SA["0025: ScoreAppeal<br/>model"]
        M_AL["0026: AuditLog<br/>immutable model"]
        M_CLIENT["0027: Client<br/>add expected_next_order,<br/>normalized_name_hash"]
        M_DL --> M_SA
        M_SA --> M_AL
    end

    subgraph PHASE_3["Phase 3: Telephony Prep"]
        M_CALL["0028: CallRecord<br/>model"]
        M_WH["0029: TelephonyWebhookLog<br/>model"]
        M_CALL --> M_WH
    end

    TEST_PARITY --> M_CR
    M_CFG --> M_DL
    M_NSS --> M_CLIENT
    M_AL --> M_CALL

    style PHASE_0 fill:#3c1518,stroke:#69140e,color:#f2b5d4
    style PHASE_1 fill:#1b4332,stroke:#2d6a4f,color:#d8f3dc
    style PHASE_2 fill:#14213d,stroke:#fca311,color:#e5e5e5
    style PHASE_3 fill:#023047,stroke:#219ebc,color:#8ecae6
```

---

## 11. URL Structure Map: Текущие + Новые endpoints

```mermaid
mindmap
  root["management/"]
    AUTH
      login/
      logout/
    CLIENTS
      clients/ID/delete/
    ADMIN_PANEL
      admin-panel/
      admin-panel/user/ID/clients/
      admin-panel/invoices/ID/approve/
      admin-panel/invoices/ID/reject/
      admin-panel/payouts/settings/save/
      admin-panel/payouts/request/ID/approve/
      admin-panel/payouts/request/ID/reject/
      admin-panel/payouts/request/ID/paid/
      admin-panel/payouts/manual/
      admin-panel/payouts/adjust/
      🆕 admin-panel/readiness/
      🆕 admin-panel/economics/
      🆕 admin-panel/freeze/
    REPORTS
      reports/
      reports/send/
    STATS
      stats/
      stats/admin/
      stats/admin/ID/
      stats/advice/dismiss/
      activity/pulse/
    SHOPS
      shops/
      shops/api/save/
      shops/api/detail/ID/
      shops/api/contact/add/
      shops/api/next-contact/
      shops/api/inventory/move/
      shops/api/ID/delete/
    INVOICES
      invoices/ ... 6 endpoints
    CONTRACTS
      contracts/ ... 5 endpoints
    CP_EMAIL
      commercial-offer/email/ ... 8 endpoints
    LEADS
      leads/api/create/
      leads/api/ID/detail/
      leads/api/ID/process/
    PARSING
      parsing/ ... 7 endpoints
    NEW_ENDPOINTS
      🆕 appeals/api/submit/
      🆕 appeals/api/ID/resolve/
      🆕 score/api/explain/
      🆕 mosaic/api/shadow/
      🆕 telephony/webhook/
    TG_BOT
      tg-manager/webhook/TOKEN/
```

---

## 12. ComponentReadiness State Machine

```mermaid
stateDiagram-v2
    [*] --> DORMANT : Initial state (seed)
    
    DORMANT --> SHADOW : Admin activates shadow
    SHADOW --> ACTIVE : Activation gate passed
    SHADOW --> DORMANT : Issues found, rollback
    ACTIVE --> SHADOW : Incident, temporary disable
    
    note right of DORMANT
        Component not computed
        No UI surface
        No data flow
    end note
    
    note right of SHADOW
        Component computed
        Visible to admin only
        No payroll impact
        Diagnostic/coaching use
    end note
    
    note right of ACTIVE
        Component computed
        Visible to all
        Participates in production score
        May affect payroll
    end note
```

---

## 13. KPD ↔ MOSAIC Component Mapping

```mermaid
flowchart LR
    subgraph KPD_COMPONENTS["KPD Components"]
        K_EFFORT_ACT["Effort: active_seconds"]
        K_EFFORT_PTS["Effort: points"]
        K_QUALITY["Quality: success_weighted"]
        K_OPS_CP["Ops: CP emails sent"]
        K_OPS_SHOPS["Ops: shops created"]
        K_OPS_INV["Ops: invoices created"]
        K_PEN_FU["Penalty: missed followups"]
        K_PEN_REP["Penalty: late/missing reports"]
        K_PEN_PLAN["Penalty: followup plan missing"]
    end

    subgraph MOSAIC_AXES["MOSAIC Axes"]
        M_RESULT["Result (0.40)"]
        M_SF["SourceFairness (0.15)"]
        M_PROCESS["Process (0.15)"]
        M_FU["FollowUp (0.15)"]
        M_DQ["DataQuality (0.10)"]
        M_VC["VerifiedComm (0.05)"]
    end

    K_EFFORT_ACT -.->|"❓ GAP: no mapping"| M_PROCESS
    K_EFFORT_PTS -->|"partial"| M_RESULT
    K_QUALITY -->|"replaces with EWR"| M_RESULT
    K_OPS_CP -->|"partial"| M_PROCESS
    K_OPS_SHOPS -->|"partial"| M_PROCESS
    K_OPS_INV -->|"revenue signal"| M_RESULT
    K_PEN_FU -->|"direct"| M_FU
    K_PEN_REP -->|"partial"| M_DQ
    K_PEN_PLAN -->|"partial"| M_FU

    style KPD_COMPONENTS fill:#3c1518,stroke:#69140e,color:#f2b5d4
    style MOSAIC_AXES fill:#0d1b2a,stroke:#1b3a4b,color:#a9d6e5
```

---

*Диаграммы подготовлены: Gemini 2.5 Pro (Antigravity), 2026-03-13*
*Формат: Mermaid — рендерится в GitHub, GitLab, Jetbrains IDE, VS Code*
