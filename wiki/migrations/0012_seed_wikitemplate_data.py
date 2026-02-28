"""
Data migration: seed the 5 built-in PM wiki page templates.
These are read-only system records — not created or edited by users.
"""

from django.db import migrations

TEMPLATES = [
    {
        "name": "Project Charter",
        "description": "Define project purpose, scope, stakeholders, timeline, and budget.",
        "category_name": "Project Management",
        "icon": "file-contract",
        "color": "#3498db",
        "order": 1,
        "content": """\
# Project Charter

> **Document Status:** Draft | **Version:** 1.0 | **Date:** *(fill in)*

---

## 1. Project Overview

| Field | Details |
|---|---|
| **Project Name** | *(enter project name)* |
| **Project Manager** | *(enter name)* |
| **Sponsor** | *(enter name)* |
| **Start Date** | *(DD/MM/YYYY)* |
| **Target End Date** | *(DD/MM/YYYY)* |
| **Department / Team** | *(enter department)* |

---

## 2. Project Objective

*(Describe the business problem this project solves and the value it will deliver. Keep to 2–3 sentences.)*

---

## 3. Scope

### In Scope
- *(Item 1)*
- *(Item 2)*
- *(Item 3)*

### Out of Scope
- *(Item 1)*
- *(Item 2)*

---

## 4. Stakeholders

| Name | Role | Responsibility | Contact |
|---|---|---|---|
| *(Name)* | Project Sponsor | Final approval & funding | *(email)* |
| *(Name)* | Project Manager | Day-to-day delivery | *(email)* |
| *(Name)* | Tech Lead | Technical decisions | *(email)* |
| *(Name)* | Business Analyst | Requirements gathering | *(email)* |
| *(Name)* | End User Rep | Acceptance testing | *(email)* |

---

## 5. High-Level Timeline

| Phase | Description | Start | End |
|---|---|---|---|
| Initiation | Project kick-off, charter sign-off | *(date)* | *(date)* |
| Planning | Requirements, design, resource planning | *(date)* | *(date)* |
| Execution | Development / implementation | *(date)* | *(date)* |
| Testing | QA, UAT, bug fixes | *(date)* | *(date)* |
| Closure | Go-live, handover, lessons learned | *(date)* | *(date)* |

---

## 6. Budget Estimate

| Category | Estimated Cost | Notes |
|---|---|---|
| Personnel | *(amount)* | *(e.g. contractor days)* |
| Software / Licences | *(amount)* | |
| Infrastructure | *(amount)* | |
| Training | *(amount)* | |
| Contingency (10%) | *(amount)* | |
| **Total** | ***(amount)*** | |

---

## 7. Success Criteria

- [ ] *(Measurable criterion 1 — e.g. "System processes 1,000 orders/day with <2 s latency")*
- [ ] *(Measurable criterion 2)*
- [ ] *(Measurable criterion 3)*

---

## 8. Known Risks (High Level)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| *(Risk description)* | High / Med / Low | High / Med / Low | *(mitigation plan)* |
| *(Risk description)* | | | |

---

## 9. Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Project Sponsor | | | |
| Project Manager | | | |
| Department Head | | | |
""",
    },
    {
        "name": "Issue Log",
        "description": "Track open issues, owners, priorities, and resolutions throughout the project.",
        "category_name": "Project Management",
        "icon": "exclamation-triangle",
        "color": "#e74c3c",
        "order": 2,
        "content": """\
# Issue Log

**Project:** *(enter project name)*
**Project Manager:** *(enter name)*
**Last Updated:** *(DD/MM/YYYY)*

---

## How to Use This Log

- Add a new row for every issue raised during the project.
- Set **Priority**: 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low
- Set **Status**: Open · In Progress · Resolved · Closed · Deferred
- **Issue ID** format: `ISS-001`, `ISS-002`, …

---

## Issue Register

| Issue ID | Date Raised | Description | Priority | Raised By | Owner | Due Date | Status | Resolution / Notes |
|---|---|---|---|---|---|---|---|---|
| ISS-001 | *(date)* | *(Describe the issue clearly)* | 🔴 Critical | *(name)* | *(name)* | *(date)* | Open | |
| ISS-002 | *(date)* | *(Describe the issue clearly)* | 🟠 High | *(name)* | *(name)* | *(date)* | In Progress | *(progress note)* |
| ISS-003 | *(date)* | *(Describe the issue clearly)* | 🟡 Medium | *(name)* | *(name)* | *(date)* | Resolved | *(how it was resolved)* |

---

## Summary Statistics

| Status | Count |
|---|---|
| Open | |
| In Progress | |
| Resolved | |
| Closed | |
| **Total** | |

---

## Escalation Path

- **Critical/High issues unresolved >2 days** → escalate to Project Sponsor
- **Blockers affecting delivery date** → flag in next status report
""",
    },
    {
        "name": "Risk Register",
        "description": "Identify, assess, and track project risks with mitigation strategies.",
        "category_name": "Project Management",
        "icon": "shield-alt",
        "color": "#f39c12",
        "order": 3,
        "content": """\
# Risk Register

**Project:** *(enter project name)*
**Project Manager:** *(enter name)*
**Last Updated:** *(DD/MM/YYYY)*

---

## Scoring Guide

**Probability:** 1 = Rare · 2 = Unlikely · 3 = Possible · 4 = Likely · 5 = Almost Certain
**Impact:** 1 = Negligible · 2 = Minor · 3 = Moderate · 4 = Major · 5 = Catastrophic
**Risk Score** = Probability × Impact

| Score | Rating |
|---|---|
| 1–4 | 🟢 Low |
| 5–9 | 🟡 Medium |
| 10–16 | 🟠 High |
| 17–25 | 🔴 Critical |

---

## Risk Register

| Risk ID | Date Identified | Description | Category | Probability (1–5) | Impact (1–5) | Risk Score | Rating | Mitigation Strategy | Owner | Response | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RSK-001 | *(date)* | *(Describe the risk)* | Schedule | 3 | 4 | 12 | 🟠 High | *(mitigation action)* | *(name)* | Mitigate | Open |
| RSK-002 | *(date)* | *(Describe the risk)* | Budget | 2 | 5 | 10 | 🟠 High | *(mitigation action)* | *(name)* | Transfer | Open |
| RSK-003 | *(date)* | *(Describe the risk)* | Resource | 4 | 3 | 12 | 🟠 High | *(mitigation action)* | *(name)* | Mitigate | Monitoring |

---

## Risk Response Types

- **Avoid** — change the plan to eliminate the risk
- **Mitigate** — reduce probability or impact
- **Transfer** — shift risk to a third party (e.g. insurance, contract clause)
- **Accept** — acknowledge the risk and prepare a contingency plan

---

## Review Schedule

Risk register to be reviewed: **every sprint / fortnightly** *(choose one)*
Next scheduled review: *(date)*
""",
    },
    {
        "name": "Meeting Minutes",
        "description": "Structured template for recording decisions, discussion notes, and action items.",
        "category_name": "Meeting Notes",
        "icon": "calendar-alt",
        "color": "#2ecc71",
        "order": 4,
        "content": """\
# Meeting Minutes

---

## Meeting Details

| Field | Details |
|---|---|
| **Meeting Title** | *(e.g. Sprint Planning — Sprint 12)* |
| **Date & Time** | *(DD/MM/YYYY · HH:MM – HH:MM)* |
| **Location / Link** | *(room name or video call URL)* |
| **Facilitator** | *(name)* |
| **Note Taker** | *(name)* |
| **Next Meeting** | *(DD/MM/YYYY · HH:MM)* |

---

## Attendees

| Name | Role | Present |
|---|---|---|
| *(name)* | *(role)* | ✅ |
| *(name)* | *(role)* | ✅ |
| *(name)* | *(role)* | ❌ Apologies |

---

## Agenda

1. *(Agenda item 1)*
2. *(Agenda item 2)*
3. *(Agenda item 3)*
4. AOB (Any Other Business)

---

## Discussion Notes

### 1. *(Agenda Item 1)*
*(Summary of discussion, key points raised, any disagreements noted)*

### 2. *(Agenda Item 2)*
*(Summary of discussion)*

### 3. *(Agenda Item 3)*
*(Summary of discussion)*

### 4. AOB
*(Any other business discussed)*

---

## Decisions Made

- **Decision 1:** *(State the decision clearly)*
- **Decision 2:** *(State the decision clearly)*
- **Decision 3:** *(State the decision clearly)*

---

## Action Items

| # | Action | Owner | Due Date | Status |
|---|---|---|---|---|
| 1 | *(Describe the action)* | *(name)* | *(date)* | Open |
| 2 | *(Describe the action)* | *(name)* | *(date)* | Open |
| 3 | *(Describe the action)* | *(name)* | *(date)* | Open |

---

## Next Meeting

**Date & Time:** *(DD/MM/YYYY · HH:MM)*
**Location / Link:** *(TBC)*
**Proposed Agenda:**
1. *(Item 1)*
2. Review action items from today*
""",
    },
    {
        "name": "RACI Matrix",
        "description": "Clarify ownership with a Responsible, Accountable, Consulted, Informed chart.",
        "category_name": "Project Management",
        "icon": "table",
        "color": "#9b59b6",
        "order": 5,
        "content": """\
# RACI Matrix

**Project:** *(enter project name)*
**Project Manager:** *(enter name)*
**Version:** 1.0 | **Date:** *(DD/MM/YYYY)*

---

## RACI Key

| Letter | Role | Description |
|---|---|---|
| **R** | **Responsible** | Does the work. At least one R per row. |
| **A** | **Accountable** | Owns the outcome. Signs off. Only one A per row. |
| **C** | **Consulted** | Provides input before the work is done (two-way). |
| **I** | **Informed** | Kept up to date after decisions / work is done (one-way). |

---

## Role Definitions

| Role / Stakeholder | Person(s) |
|---|---|
| Project Manager | *(name)* |
| Tech Lead | *(name)* |
| Business Analyst | *(name)* |
| Designer | *(name)* |
| QA Engineer | *(name)* |
| Project Sponsor | *(name)* |

---

## RACI Chart

| Task / Deliverable | Project Manager | Tech Lead | Business Analyst | Designer | QA Engineer | Project Sponsor |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Project Charter | A | C | C | — | — | R |
| Requirements Gathering | C | C | R | C | C | I |
| Technical Architecture | I | A/R | C | — | C | I |
| UI/UX Design | I | C | C | A/R | C | I |
| Development / Build | I | A | I | I | C | I |
| Test Plan & Execution | I | C | C | I | A/R | I |
| UAT Sign-Off | A | I | C | I | I | R |
| Go-Live Decision | A | C | C | I | C | R |
| Post-Launch Review | R | C | C | C | C | I |

> **Tip:** Add/remove rows for each deliverable in your project. Adjust columns for your actual team roles.

---

## Notes

*(Record any specific ownership clarifications or exceptions here)*
""",
    },
]


def seed_templates(apps, schema_editor):
    WikiTemplate = apps.get_model("wiki", "WikiTemplate")
    objs = [WikiTemplate(**tpl) for tpl in TEMPLATES]
    WikiTemplate.objects.bulk_create(objs)


def remove_templates(apps, schema_editor):
    WikiTemplate = apps.get_model("wiki", "WikiTemplate")
    WikiTemplate.objects.filter(name__in=[t["name"] for t in TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0011_add_wikitemplate_model"),
    ]

    operations = [
        migrations.RunPython(seed_templates, reverse_code=remove_templates),
    ]
