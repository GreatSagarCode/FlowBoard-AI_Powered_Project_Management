# FlowBoard Project — Final Audit Report

**Project:** AI-Powered Project Management SaaS
**Tech Stack:** Flask, Jinja2, Tailwind CSS, SQLite, scikit-learn
**Audit Date:** 2026-06-11

---

## 1. Executive Summary

The application is largely functional but has several **backend-frontend mismatches**, **orphaned code**, and an **ML pipeline that needs hardening** for production use. The core architecture (Flask Blueprints, SQLAlchemy models, Jinja templates) is solid. The most critical issues are:

- A broken drag-and-drop endpoint referenced by an orphaned template
- JavaScript scope bugs preventing the task detail slide-over from working
- ML models that are black-box `.joblib` files with no training pipeline, no evaluation metrics, and a fake "AI description generator"
- Missing risk detection model (listed as MANDATORY in requirements)

---

## 2. Frontend vs Backend Feature Gaps

### 2.1 Broken Endpoints

| Feature | Frontend Expects | Backend Provides | Status |
|---------|-----------------|------------------|--------|
| Kanban drag-drop | `POST /tasks/update_status` (in `kanban.html`) | No such route; correct route is `/tasks/<id>/update` with `{field: "status", value: ...}` | **BROKEN** |
| Task detail panel JS | `updateTaskStatus()`, `deleteTask()`, `createSubtask()` as globals | Functions are scoped inside `DOMContentLoaded` in `project_details.html` | **BROKEN** — injected HTML cannot access them |
| Task AI suggestions (task modal) | Calls `/ml/suggest` expecting full payload | `tasks/routes.py` version returns only `suggested_description` | **PARTIAL** |

### 2.2 UI Restrictions Missing Backend Support

| Feature | Backend Allows | Frontend Restricts | Impact |
|---------|---------------|-------------------|--------|
| Task status | Any string (default "To Do") | Only "To Do", "In Progress", "Done" in forms | `Review` status unreachable via UI |
| Priority | Any string (Highest/High/Medium/Low/Lowest) | Only Low/Medium/High | Highest/Lowest cannot be set |
| Issue types | Any string | Task/Bug/Feature/Epic/Story/Design/Frontend/Backend/DevOps/Docs | Model predicts different categories (Dev/Design/Testing/Docs) |

### 2.3 Dead Code

- `app/templates/tasks/kanban.html` — No route renders this template. It duplicates the board tab inside `project_details.html` and references the broken `/tasks/update_status` endpoint.
- `tasks/routes.py:ml_suggest()` — Redundant with `main/routes.py:ml_suggest()`; returns incomplete payload.
- `app/projects/routes.py` references `projects.backlog` as a route in `backlog.html` (`href="{{ url_for('projects.backlog', ...) }}"`) but no such endpoint exists; the actual view is rendered via `project_details?tab=backlog`.

### 2.4 Flash Messages in AJAX

`tasks/routes.py:127` calls `flash()` inside `batch_delete_tasks()` then returns `jsonify()`.  
Flash messages require a redirect to be displayed; XHR/AJAX responses never render them. These should return structured JSON errors instead.

---

## 3. ML Pipeline Analysis

### 3.1 Current State

Three trained models exist as `.joblib` files:
- `ml/models/task_classifier.joblib`
- `ml/models/duration_predictor.joblib`
- `ml/models/priority_classifier.joblib`

`ml/inference.py` loads them via `MLService` singleton.

### 3.2 Critical Issues

1. **No training script in repository**  
   Models are black boxes. There is no `train.py`, no dataset file, no feature pipeline, and no evaluation script. Cannot retrain, audit, or validate.
2. **Fake AI description generator**  
   `ml/inference.py:generate_project_description()` is a hardcoded keyword matcher over a 10-entry dictionary. It returns template strings, not generated text. This is not ML.
3. **Priority label mismatch**  
   If the model was trained on `['Low','Medium','High']` but the frontend allows `['Low','Medium','High','Highest']`, the ML can never produce `Highest` predictions.
4. **Category vs issue_type mismatch**  
   Model predicts `Dev / Design / Testing / Docs`. Frontend issue types are `Task / Feature / Bug / Epic / Story / Improvement / DevOps`. These taxonomies are completely different. The ML category is stored but unused for filtering or routing.
5. **No model metadata**  
   No version tracking, training date, accuracy metrics, or feature schema. Impossible to know when to retrain.
6. **Missing risk detection**  
   Requirement explicitly states risk detection is MANDATORY. No `risk_detector.joblib` exists. Current "risk" is only inline Python (overdue check in `tasks/routes.py:auto_move_overdue_tasks`), not an ML model.
7. **No offline evaluation**  
   Cannot verify accuracy, precision, recall, or MAE without ad-hoc notebooks.

### 3.3 Where ML Is Used vs. Should Be Used

| Touchpoint | Current | Gap |
|-----------|---------|-----|
| Project creation modal | Description + priority + date | Missing deadline risk scoring |
| Task creation modal | Broken (only description) | Should use: category, duration, priority, risk |
| Task detail panel | Shows category + duration | Missing risk badge, smart assignee |
| Analytics tab | Category distribution chart | Missing risk distribution, overdue prediction |
| Board/Backlog | None | Risk badges, smart sort by risk |
| Notifications | Rule-based overdue only | ML "at risk" notification 2 days before predicted deadline |

---

## 4. Remediation Plan

### Phase A: Fix Broken Features (2–3 hours)

1. **Remove orphaned `kanban.html`** or add a serving route. Board tab in `project_details.html` supersedes it.
2. **Fix JavaScript scope**: In `project_details.html`, attach `updateTaskStatus`, `deleteTask`, `createSubtask`, `updateTaskField` to `window` so injected slide-over panel HTML can access them.
3. **Fix Flash-in-AJAX**: Replace `flash()` in `tasks/routes.py` AJAX endpoints with `jsonify` error responses.
4. **Add `Highest`/`Lowest` to priority dropdowns** in `project_details.html` and `task_snippet.html`.
5. **Bind `initializeBacklog()`**: Call it inside `showTab('backlog')`.
6. **Add `Review` status** to task creation form and status update dropdowns.
7. **Fix task modal AI**: Ensure it calls the `/ml/suggest` endpoint that returns full payload — ensure it hits the `main` blueprint route.

### Phase B: ML Training Pipeline (3–4 hours)

**New file: `ml/train.py`**
```
- Load labeled tasks from `ml/data/tasks.jsonl`
- TF-IDF + MultinomialNB    → task_classifier.joblib
- TF-IDF + Ridge Regressor   → duration_predictor.joblib
- TF-IDF + LogisticRegression → priority_classifier.joblib
- TF-IDF + RandomForest     → risk_detector.joblib
- Evaluate: accuracy/F1/MAE
- Save: models + metadata JSON
```

**New file: `ml/data/tasks.jsonl`** — ~300 annotated examples  
**New file: `ml/evaluate.py`** — Load models, evaluate on holdout set, print metrics

### Phase C: Replace Fake Description Generator (1–2 hours)

Replace the hardcoded keyword dict in `generate_project_description()` with a template registry loaded from `ml/data/description_templates.json` keyed by category. Deterministic, no external API, no fake ML.

### Phase D: Add Risk Detection (2–3 hours)

1. Train `risk_detector.joblib` on `[title, description, due_date_delta, priority_numeric, story_points, assignee_task_count, project_health]`.
2. Add `predict_risk(task, user_workload)` to `ml/inference.py`.
3. Auto-compute on task create and expose via API.
4. Frontend: risk badge on task cards and slide-over.
5. Background: auto-notify when risk score exceeds threshold.

### Phase E: Admin ML Dashboard (2–3 hours, optional)

- Route `/admin/ml` (admin only): model version, training date, accuracy.
- DB table `ml_model_version` for deployment tracking.
- "Retrain" button that spawns `ml/train.py` subprocess.

---

## 5. Priority Execution Order

1. **Phase A** — Fix broken features; unbreak existing UI
2. **Phase B** — Reproducible training pipeline; train all 4 models
3. **Phase C** — Remove fake AI description generator
4. **Phase D** — Wire risk detection into routes + frontend (fulfills MANDATORY requirement)
5. **Phase E** — Admin ML dashboard for observability

---

## 6. Missing Features Summary

| # | Gap | Severity | Phase |
|---|-----|----------|-------|
| 1 | `tasks/update_status` endpoint does not exist (board drag broken) | Critical | A |
| 2 | Slide-over panel JS functions not global (task detail broken) | Critical | A |
| 3 | `flash()` in AJAX endpoints | Medium | A |
| 4 | Priority filter omits Highest/Lowest | Medium | A |
| 5 | Task status missing Review option | Medium | A |
| 6 | Backlog drag `initializeBacklog` never called | Medium | A |
| 7 | Orphaned `kanban.html` template | Low | A |
| 8 | No ML training pipeline (black-box models) | High | B |
| 9 | Fake AI description generator | High | C |
| 10 | No risk detection model | High (MANDATORY) | D |
| 11 | No model metadata/evaluation | High | B |

---

## 7. Key Files to Modify

- `app/templates/projects/project_details.html` — JS scope fixes, priority filter, backlog init
- `app/templates/tasks/task_snippet.html` — priority dropdown
- `app/templates/tasks/kanban.html` — DELETE or fix
- `app/tasks/routes.py` — Fix flash, add/redirect update_status, remove redundant ml_suggest
- `app/projects/routes.py` — Fix backlog route name if referenced
- `ml/inference.py` — Replace fake generator, add risk prediction
- `ml/train.py` — NEW
- `ml/evaluate.py` — NEW
- `ml/data/tasks.jsonl` — NEW
- `ml/data/description_templates.json` — NEW
