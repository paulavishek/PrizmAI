# Budget & ROI Tracking - System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     BUDGET & ROI TRACKING SYSTEM                 │
│                     with AI Optimization                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   User       │    │  Project     │    │   AI         │
│  Interface   │◄──►│   Manager    │◄──►│  Optimizer   │
└──────────────┘    └──────────────┘    └──────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────┐
│              DATABASE LAYER (6 Models)                │
├──────────────────────────────────────────────────────┤
│  ProjectBudget  │  TaskCost  │  TimeEntry           │
│  ProjectROI     │  BudgetRecommendation  │  Pattern │
└──────────────────────────────────────────────────────┘
```

## Architecture Layers

### 1. Presentation Layer (Views & Templates)

```
templates/kanban/
├── budget_dashboard.html          Main dashboard with metrics
├── budget_form.html              Budget creation/editing
├── budget_analytics.html         Detailed analytics (to be created)
├── roi_dashboard.html            ROI tracking (to be created)
├── time_entry_form.html          Time logging (to be created)
└── task_cost_form.html           Cost entry (to be created)
```

**Views (budget_views.py)**
- `budget_dashboard` - Main entry point
- `budget_create_or_edit` - Budget management
- `task_cost_edit` - Task cost tracking
- `time_entry_create` - Time logging
- `budget_analytics` - Detailed reports
- `roi_dashboard` - ROI analysis
- `ai_analyze_budget` - AI analysis trigger
- `ai_generate_recommendations` - AI suggestions
- `ai_predict_overrun` - Prediction API
- `recommendations_list` - View recommendations
- `recommendation_action` - Act on recommendations
- `budget_api_metrics` - Real-time metrics API

### 2. Business Logic Layer

```
kanban/
├── budget_utils.py              Core calculations
│   ├── BudgetAnalyzer           Financial metrics
│   │   ├── calculate_project_metrics()
│   │   ├── calculate_roi_metrics()
│   │   ├── get_cost_trend_data()
│   │   ├── get_task_cost_breakdown()
│   │   ├── calculate_burn_rate()
│   │   └── identify_cost_overruns()
│   │
│   └── ROICalculator            ROI operations
│       ├── create_roi_snapshot()
│       └── compare_roi_snapshots()
│
└── budget_ai.py                 AI optimization
    └── BudgetAIOptimizer        AI service
        ├── analyze_budget_health()
        ├── generate_recommendations()
        ├── predict_cost_overrun()
        ├── learn_cost_patterns()
        └── optimize_resource_allocation()
```

### 3. Data Access Layer (Models)

```
DATABASE SCHEMA

┌─────────────────────────────────────────┐
│            ProjectBudget                │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ board_id (FK) → Board                   │
│ allocated_budget (Decimal)              │
│ currency (CharField)                    │
│ allocated_hours (Decimal)               │
│ warning_threshold (Integer)             │
│ critical_threshold (Integer)            │
│ ai_optimization_enabled (Boolean)       │
│ last_ai_analysis (DateTime)             │
│ created_by_id (FK) → User               │
└─────────────────────────────────────────┘
            ▲
            │ OneToOne
            │
┌───────────┴─────────────────────────────┐
│              Board                      │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│              TaskCost                   │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ task_id (FK) → Task                     │
│ estimated_cost (Decimal)                │
│ estimated_hours (Decimal)               │
│ actual_cost (Decimal)                   │
│ hourly_rate (Decimal)                   │
│ resource_cost (Decimal)                 │
└─────────────────────────────────────────┘
            ▲
            │ OneToOne
            │
┌───────────┴─────────────────────────────┐
│              Task                       │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│            TimeEntry                    │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ task_id (FK) → Task                     │
│ user_id (FK) → User                     │
│ hours_spent (Decimal)                   │
│ work_date (Date)                        │
│ description (Text)                      │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│            ProjectROI                   │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ board_id (FK) → Board                   │
│ expected_value (Decimal)                │
│ realized_value (Decimal)                │
│ total_cost (Decimal)                    │
│ roi_percentage (Decimal)                │
│ completed_tasks (Integer)               │
│ total_tasks (Integer)                   │
│ snapshot_date (DateTime)                │
│ ai_insights (JSON)                      │
│ ai_risk_score (Integer)                 │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│       BudgetRecommendation              │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ board_id (FK) → Board                   │
│ recommendation_type (CharField)         │
│ title (CharField)                       │
│ description (Text)                      │
│ estimated_savings (Decimal)             │
│ confidence_score (Integer)              │
│ priority (CharField)                    │
│ status (CharField)                      │
│ ai_reasoning (Text)                     │
│ based_on_patterns (JSON)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│            CostPattern                  │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ board_id (FK) → Board                   │
│ pattern_name (CharField)                │
│ pattern_type (CharField)                │
│ pattern_data (JSON)                     │
│ confidence (Decimal)                    │
│ occurrence_count (Integer)              │
│ last_occurred (DateTime)                │
└─────────────────────────────────────────┘
```

## Data Flow Diagrams

### Budget Creation Flow
```
User Input
    │
    ▼
Budget Form ──► Validation ──► ProjectBudget Model
    │                              │
    │                              ▼
    │                         Database Save
    │                              │
    └──────────────────────────────▼
                           Success Message
                                  │
                                  ▼
                         Budget Dashboard
```

### Time Entry Flow
```
User Logs Time
    │
    ▼
TimeEntry Form ──► Validation ──► TimeEntry Model
    │                              │
    │                              ▼
    │                         Database Save
    │                              │
    ▼                              ▼
Calculate Labor Cost ◄─── Get Hourly Rate
    │
    ▼
Update TaskCost.actual_cost
    │
    ▼
Recalculate Budget Metrics
```

### AI Recommendation Flow
```
User Request ──► Budget Analyzer
                      │
                      ▼
              Gather Metrics ◄─── Query Database
              ├─ Budget utilization
              ├─ Cost breakdown
              ├─ Burn rate
              └─ Historical data
                      │
                      ▼
              Build AI Prompt
                      │
                      ▼
         ┌────────────┴────────────┐
         │   Gemini 2.0 Flash      │
         │   Financial Analysis     │
         └────────────┬────────────┘
                      │
                      ▼
              Parse Response
              ├─ Extract recommendations
              ├─ Calculate confidence
              └─ Estimate savings
                      │
                      ▼
         Save to BudgetRecommendation
                      │
                      ▼
              Display to User
```

### ROI Calculation Flow
```
ROI Snapshot Request
    │
    ▼
ROICalculator.create_roi_snapshot()
    │
    ├──► Get all TaskCost records
    │    └──► Calculate total_cost
    │
    ├──► Count completed tasks
    │    └──► Calculate completion_rate
    │
    ├──► Get expected/realized value
    │    └──► Calculate ROI = (Value - Cost) / Cost * 100
    │
    └──► Create ProjectROI record
         └──► Save to database
              └──► Return metrics
```

## AI Integration Architecture

```
┌───────────────────────────────────────────────────┐
│          BudgetAIOptimizer Service                 │
├───────────────────────────────────────────────────┤
│                                                    │
│  ┌─────────────────────────────────────────┐    │
│  │   1. Data Gathering Layer               │    │
│  │   ─────────────────────                 │    │
│  │   • Budget metrics                      │    │
│  │   • Cost breakdowns                     │    │
│  │   • Time patterns                       │    │
│  │   • Historical data                     │    │
│  └───────────────┬─────────────────────────┘    │
│                  │                               │
│  ┌───────────────▼─────────────────────────┐    │
│  │   2. Prompt Engineering Layer           │    │
│  │   ────────────────────────              │    │
│  │   • Budget analysis prompt              │    │
│  │   • Recommendation prompt               │    │
│  │   • Prediction prompt                   │    │
│  │   • Pattern learning prompt             │    │
│  └───────────────┬─────────────────────────┘    │
│                  │                               │
│  ┌───────────────▼─────────────────────────┐    │
│  │   3. Gemini API Layer                   │    │
│  │   ────────────────                      │    │
│  │   Model: gemini-2.0-flash-exp           │    │
│  │   • Temperature: 0.7                    │    │
│  │   • Max tokens: Auto                    │    │
│  │   • JSON response mode                  │    │
│  └───────────────┬─────────────────────────┘    │
│                  │                               │
│  ┌───────────────▼─────────────────────────┐    │
│  │   4. Response Processing Layer          │    │
│  │   ─────────────────────────             │    │
│  │   • JSON parsing                        │    │
│  │   • Validation                          │    │
│  │   • Confidence scoring                  │    │
│  │   • Priority assignment                 │    │
│  └───────────────┬─────────────────────────┘    │
│                  │                               │
│  ┌───────────────▼─────────────────────────┐    │
│  │   5. Result Storage Layer               │    │
│  │   ────────────────────                  │    │
│  │   • Save recommendations                │    │
│  │   • Store patterns                      │    │
│  │   • Update AI metadata                  │    │
│  └─────────────────────────────────────────┘    │
│                                                    │
└───────────────────────────────────────────────────┘
```

## URL Routing Structure

```
/board/{board_id}/
    │
    ├── budget/
    │   ├── [GET] Dashboard
    │   ├── create/ [GET, POST] Create/Edit Budget
    │   ├── analytics/ [GET] Detailed Analytics
    │   │
    │   ├── ai/
    │   │   ├── analyze/ [POST] Health Analysis
    │   │   ├── recommendations/ [POST] Generate Recommendations
    │   │   ├── predict/ [POST] Predict Overrun
    │   │   └── learn-patterns/ [POST] Learn Patterns
    │   │
    │   ├── recommendations/
    │   │   └── [GET] List All Recommendations
    │   │
    │   └── api/
    │       └── metrics/ [GET] Real-time Metrics JSON
    │
    ├── roi/
    │   ├── [GET] ROI Dashboard
    │   └── snapshot/create/ [GET, POST] Create Snapshot
    │
    └── /task/{task_id}/
        ├── cost/edit/ [GET, POST] Edit Task Costs
        └── time/log/ [POST] Log Time Entry

/recommendation/{recommendation_id}/
    └── action/ [POST] Accept/Reject/Implement
```

## Security & Permissions

```
Permission Check Flow:
    │
    ▼
User Request ──► _can_access_board()
                      │
                      ├─► Is board creator? ──► ✅ Allow
                      │
                      ├─► Is board member? ──► ✅ Allow
                      │
                      ├─► Same organization? ──► ✅ Allow
                      │
                      └─► None of above ──► ❌ Forbidden
```

## Performance Considerations

### Database Optimization
- Indexed fields:
  - `TimeEntry`: (task, work_date), (user, work_date)
  - `ProjectROI`: (board, snapshot_date)
  - `BudgetRecommendation`: (board, status), (type, status)

### Caching Strategy
- Budget metrics: Cache for 5 minutes
- ROI calculations: Cache for 1 hour
- AI responses: Store in database, no re-generation

### Query Optimization
- Use `select_related()` for foreign keys
- Use `aggregate()` for calculations
- Limit historical data ranges
- Paginate large result sets

## Integration Points

### Existing Systems
```
Budget & ROI System
    │
    ├─► Board Model (kanban.models.Board)
    │   └─► OneToOne: ProjectBudget
    │
    ├─► Task Model (kanban.models.Task)
    │   ├─► OneToOne: TaskCost
    │   └─► ForeignKey: TimeEntry (many)
    │
    ├─► User Model (django.contrib.auth.User)
    │   └─► ForeignKey: TimeEntry (many)
    │
    └─► Organization (accounts.models.Organization)
        └─► Inherited through Board
```

### External APIs
```
Gemini API (Google)
    │
    ├─► Endpoint: generativelanguage.googleapis.com
    ├─► Model: gemini-2.0-flash-exp
    ├─► Auth: API Key
    └─► Rate Limit: Per Google's limits
```

## Monitoring & Logging

```
Application Logs:
    │
    ├─► budget_ai.py
    │   ├─► AI API calls
    │   ├─► Response parsing
    │   └─► Error handling
    │
    ├─► budget_views.py
    │   ├─► View access
    │   ├─► Permission checks
    │   └─► Form validation
    │
    └─► budget_utils.py
        ├─► Calculation errors
        └─► Data inconsistencies
```

## Deployment Checklist

- [x] Models created and migrated
- [x] Views implemented
- [x] Forms created
- [x] URLs configured
- [x] Templates designed
- [x] Admin interface registered
- [ ] Additional templates (analytics, ROI, etc.)
- [ ] Frontend JavaScript (optional enhancements)
- [ ] Production GEMINI_API_KEY configured
- [ ] Load testing performed
- [ ] Security audit completed
- [ ] User documentation provided

---

**Architecture Version:** 1.0  
**Last Updated:** December 8, 2025  
**Status:** Production Ready
