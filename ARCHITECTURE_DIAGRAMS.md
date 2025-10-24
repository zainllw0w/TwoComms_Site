# 📊 Диаграммы Архитектуры TwoComms

## 1. High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        Web[Web Browser]
        Mobile[Mobile App]
        Bot[Telegram Bot]
    end
    
    subgraph "Application Layer"
        Django[Django Web Server]
        Static[WhiteNoise Static Server]
    end
    
    subgraph "Business Logic Layer"
        SF[Storefront Module]
        ORD[Orders Module]
        ACC[Accounts Module]
        PC[ProductColors Module]
    end
    
    subgraph "Data Layer"
        DB[(MySQL/PostgreSQL)]
        Redis[(Redis Cache)]
        FS[File Storage]
    end
    
    subgraph "External Services"
        Mono[Monobank API]
        NP[Nova Poshta API]
        Google[Google OAuth2]
        OpenAI[OpenAI API]
        TG[Telegram API]
    end
    
    Web --> Django
    Mobile --> Django
    Bot --> TG
    
    Django --> SF
    Django --> ORD
    Django --> ACC
    Django --> PC
    Django --> Static
    
    SF --> DB
    ORD --> DB
    ACC --> DB
    PC --> DB
    
    SF --> Redis
    ORD --> Redis
    
    SF --> FS
    ACC --> FS
    
    ORD --> Mono
    ORD --> NP
    ACC --> Google
    SF --> OpenAI
    ORD --> TG
```

## 2. Module Dependencies

```mermaid
graph LR
    subgraph "Core Modules"
        Settings[twocomms/settings]
        Middleware[Middleware Stack]
    end
    
    subgraph "Independent Modules"
        ACC[accounts]
        PC[productcolors]
    end
    
    subgraph "Dependent Modules"
        SF[storefront]
        ORD[orders]
    end
    
    Settings --> Middleware
    Settings --> ACC
    Settings --> PC
    Settings --> SF
    Settings --> ORD
    
    PC --> ACC
    SF --> ACC
    SF --> PC
    ORD --> SF
    ORD --> ACC
    ORD --> PC
    
    style ACC fill:#90EE90
    style PC fill:#90EE90
    style SF fill:#FFD700
    style ORD fill:#FFA07A
```

## 3. Data Flow: Order Processing

```mermaid
sequenceDiagram
    participant User
    participant Cart
    participant Order Service
    participant Payment
    participant Telegram
    participant Nova Poshta
    
    User->>Cart: Add Products
    Cart->>Cart: Apply Promo Code
    User->>Order Service: Create Order
    
    Order Service->>Order Service: Generate Order Number
    Order Service->>Order Service: Calculate Total
    Order Service->>Order Service: Save to DB
    
    Order Service->>Payment: Request Payment
    Payment-->>Order Service: Payment Callback
    Order Service->>Order Service: Update Status
    
    Order Service->>Telegram: Send Notification
    Order Service->>User: Order Confirmation
    
    Order Service->>Nova Poshta: Create Shipment
    Nova Poshta-->>Order Service: Tracking Number
    
    Order Service->>User: Tracking Info
```

## 4. Caching Strategy

```mermaid
graph TD
    Request[HTTP Request] --> Anon{Authenticated?}
    
    Anon -->|No| VCache[View Cache<br/>300s]
    Anon -->|Yes| View[View Function]
    
    VCache --> FCache{Fragment<br/>Cached?}
    View --> FCache
    
    FCache -->|Yes| Redis[Redis Cache]
    FCache -->|No| Query[Database Query]
    
    Redis --> Template[Template Rendering]
    Query --> Cache[Cache Result]
    Cache --> Template
    
    Template --> TCache{Template<br/>Compiled?}
    TCache -->|Yes| Static[Static Files]
    TCache -->|No| Compile[Compile Template]
    Compile --> Cache2[Cache Template]
    Cache2 --> Static
    
    Static --> SCache{Static<br/>Cached?}
    SCache -->|Yes| CDN[WhiteNoise/CDN]
    SCache -->|No| Compress[Compress & Cache]
    Compress --> CDN
    
    CDN --> Response[HTTP Response]
```

## 5. Security Layers

```mermaid
graph TB
    subgraph "Transport Security"
        HTTPS[HTTPS/TLS]
        HSTS[HSTS Headers]
    end
    
    subgraph "Application Security"
        CSP[Content Security Policy]
        XSS[XSS Protection]
        CSRF[CSRF Protection]
        Frame[X-Frame-Options]
    end
    
    subgraph "Authentication"
        JWT[Session Auth]
        OAuth[Google OAuth2]
        Pass[Password Hashing]
    end
    
    subgraph "Authorization"
        Perm[Django Permissions]
        RBAC[Role-Based Access]
        Owner[Ownership Checks]
    end
    
    subgraph "Data Security"
        SQL[SQL Injection Prevention]
        Valid[Input Validation]
        Encrypt[Data Encryption]
    end
    
    HTTPS --> CSP
    HSTS --> XSS
    CSP --> JWT
    XSS --> OAuth
    CSRF --> Pass
    Frame --> Perm
    
    JWT --> SQL
    OAuth --> Valid
    Pass --> Encrypt
    Perm --> SQL
    RBAC --> Valid
    Owner --> Encrypt
```

## 6. Deployment Architecture

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/Load Balancer]
    end
    
    subgraph "Application Servers"
        App1[Django Instance 1]
        App2[Django Instance 2]
        App3[Django Instance 3]
    end
    
    subgraph "Background Workers"
        Celery1[Celery Worker 1]
        Celery2[Celery Worker 2]
        Beat[Celery Beat]
    end
    
    subgraph "Storage Layer"
        DB[(MySQL Primary)]
        DBRead[(MySQL Replica)]
        Redis[(Redis)]
        S3[File Storage]
    end
    
    subgraph "Monitoring"
        Logs[Centralized Logs]
        Metrics[Prometheus/Grafana]
        Alerts[Alerting System]
    end
    
    LB --> App1
    LB --> App2
    LB --> App3
    
    App1 --> DB
    App2 --> DB
    App3 --> DB
    
    App1 --> DBRead
    App2 --> DBRead
    App3 --> DBRead
    
    App1 --> Redis
    App2 --> Redis
    App3 --> Redis
    
    App1 --> S3
    App2 --> S3
    App3 --> S3
    
    Celery1 --> DB
    Celery2 --> DB
    Beat --> Redis
    
    App1 --> Logs
    App2 --> Logs
    App3 --> Logs
    
    Logs --> Metrics
    Metrics --> Alerts
```

## 7. Database Schema (Simplified)

```mermaid
erDiagram
    User ||--o{ UserProfile : has
    User ||--o{ Order : places
    User ||--o{ UserPoints : has
    User ||--o{ FavoriteProduct : favorites
    
    Category ||--o{ Product : contains
    Product ||--o{ ProductColorVariant : has
    Product ||--o{ ProductImage : has
    Product ||--o{ OrderItem : in
    Product ||--o{ FavoriteProduct : favorited
    
    Order ||--o{ OrderItem : contains
    Order ||--o| PromoCode : uses
    
    UserProfile ||--o| User : extends
    UserPoints ||--|| User : tracks
    
    ProductColorVariant ||--o{ ProductImage : has
    
    DropshipperOrder ||--|| Order : extends
    WholesaleOrder ||--|| Order : extends
    
    PrintProposal }o--|| User : submitted_by
    PrintProposal }o--o| PromoCode : rewards
```

## 8. Middleware Pipeline

```mermaid
graph LR
    Request[HTTP Request] --> M1[ForceHTTPSMiddleware]
    M1 --> M2[WWWRedirectMiddleware]
    M2 --> M3[SecurityMiddleware]
    M3 --> M4[SecurityHeadersMiddleware]
    M4 --> M5[WhiteNoiseMiddleware]
    M5 --> M6[ImageOptimizationMiddleware]
    M6 --> M7[SessionMiddleware]
    M7 --> M8[CommonMiddleware]
    M8 --> M9[CsrfViewMiddleware]
    M9 --> M10[AuthenticationMiddleware]
    M10 --> M11[MessageMiddleware]
    M11 --> M12[ClickjackingMiddleware]
    M12 --> M13[RedirectFallbackMiddleware]
    M13 --> M14[SimpleAnalyticsMiddleware]
    M14 --> View[View Function]
    View --> Response[HTTP Response]
```

## 9. AI Content Generation Flow

```mermaid
graph TD
    Admin[Admin Panel] -->|Trigger| CMD[Management Command]
    CMD --> Check{Check<br/>Settings}
    
    Check -->|AI Enabled| Select[Select Products]
    Check -->|AI Disabled| Skip[Skip]
    
    Select --> Loop[For Each Product]
    Loop --> Existing{Has AI<br/>Content?}
    
    Existing -->|Yes| Next1[Next Product]
    Existing -->|No| Generate[Generate Prompt]
    
    Generate --> API[OpenAI API Call]
    API --> Parse[Parse Response]
    Parse --> Save[Save to DB]
    Save --> Signal[Fire Signal]
    Signal --> Cache[Clear Cache]
    Cache --> Next2[Next Product]
    
    Next1 --> Loop
    Next2 --> Loop
    
    Loop -->|Done| Complete[Complete]
```

## 10. Dropshipping Flow

```mermaid
sequenceDiagram
    participant DS as Dropshipper
    participant Portal as Dropship Portal
    participant System as Order System
    participant Shop as TwoComms
    participant NP as Nova Poshta
    participant Customer as End Customer
    
    DS->>Portal: Browse Catalog
    Portal->>DS: Show Wholesale Prices
    
    DS->>Portal: Create Drop Order
    Portal->>System: Submit Order
    System->>System: Calculate Discount<br/>(based on history)
    System->>System: Create Order
    
    System->>Shop: Process Order
    Shop->>NP: Create Shipment
    NP-->>Shop: Tracking Number
    
    Shop->>System: Update Status
    System->>DS: Send Tracking
    
    DS->>Customer: Notify
    
    NP->>Customer: Deliver
    Customer->>NP: Receive
    
    NP->>System: Update Status
    System->>System: Award Points
    System->>DS: Update Balance
```

## 11. Performance Optimization Layers

```mermaid
graph TB
    subgraph "Frontend Optimization"
        Lazy[Lazy Loading Images]
        Compress[Gzip/Brotli Compression]
        Minify[CSS/JS Minification]
        CDN[CDN Static Assets]
    end
    
    subgraph "Application Optimization"
        ViewCache[View-Level Cache]
        FragCache[Fragment Cache]
        TemplCache[Template Cache]
        QueryOpt[Query Optimization]
    end
    
    subgraph "Database Optimization"
        Indexes[Database Indexes]
        ConnPool[Connection Pooling]
        SelectRel[Select/Prefetch Related]
        QueryCache[Query Result Cache]
    end
    
    subgraph "Infrastructure Optimization"
        Redis[Redis Cache Layer]
        DBReplica[Read Replicas]
        LoadBal[Load Balancing]
        StaticServe[Static File Serving]
    end
    
    Lazy --> ViewCache
    Compress --> FragCache
    Minify --> TemplCache
    CDN --> Redis
    
    ViewCache --> Indexes
    FragCache --> ConnPool
    TemplCache --> SelectRel
    QueryOpt --> QueryCache
    
    Indexes --> Redis
    ConnPool --> DBReplica
    SelectRel --> LoadBal
    QueryCache --> StaticServe
```

## 12. Error Handling & Monitoring

```mermaid
graph TD
    Error[Error Occurs] --> Type{Error Type}
    
    Type -->|4xx| Client[Client Error]
    Type -->|5xx| Server[Server Error]
    
    Client --> Log1[Log to File]
    Server --> Log2[Log to File]
    Server --> Sentry[Send to Sentry]
    
    Log1 --> ELK[ELK Stack]
    Log2 --> ELK
    Sentry --> Alert[Alert System]
    
    ELK --> Dashboard[Monitoring Dashboard]
    Alert --> Team[Dev Team]
    
    Dashboard --> Metrics[Metrics Analysis]
    Team --> Fix[Fix Issue]
    
    Fix --> Deploy[Deploy Fix]
    Deploy --> Monitor[Monitor]
    Monitor --> Dashboard
```

## 13. User Journey: Purchase Flow

```mermaid
graph TD
    Start[User Visits Site] --> Browse[Browse Products]
    Browse --> Filter[Filter/Search]
    Filter --> View[View Product]
    
    View --> Auth{Logged In?}
    Auth -->|No| Guest[Continue as Guest]
    Auth -->|Yes| Cart
    Guest --> Cart[Add to Cart]
    
    Cart --> Continue{Continue<br/>Shopping?}
    Continue -->|Yes| Browse
    Continue -->|No| Checkout[Go to Checkout]
    
    Checkout --> Info[Enter Info]
    Info --> Promo{Have<br/>Promo?}
    
    Promo -->|Yes| Apply[Apply Promo Code]
    Promo -->|No| Payment
    Apply --> Payment[Select Payment]
    
    Payment --> PayType{Payment<br/>Type?}
    PayType -->|Card| Online[Online Payment]
    PayType -->|COD| COD[Cash on Delivery]
    
    Online --> Gateway[Payment Gateway]
    Gateway --> Confirm[Order Confirmed]
    COD --> Confirm
    
    Confirm --> Points[Award Points]
    Points --> Notify[Send Notifications]
    Notify --> Track[Provide Tracking]
    Track --> End[Complete]
```

---

## Legend

### Status Colors

- 🟢 **Green**: Stable, Independent Module
- 🟡 **Yellow**: Core Module with Dependencies
- 🟠 **Orange**: High-Level Application Module
- 🔴 **Red**: Critical Path

### Dependency Types

- **Solid Line**: Direct Dependency
- **Dashed Line**: Indirect/Optional Dependency
- **Bold Line**: Critical Dependency

### Module Stability

- **Circle**: Stable (rarely changes)
- **Rectangle**: Semi-stable
- **Diamond**: Unstable (frequently changes)

---

## Notes

1. All diagrams represent the **current state** of the architecture as of October 24, 2025
2. External services dependencies are clearly marked
3. Cache layers are shown separately for clarity
4. Security layers are depicted in separate diagram
5. Data flow diagrams show typical user journeys

---

**Generated:** October 24, 2025  
**Tool:** Mermaid Diagrams  
**Version:** 1.0















