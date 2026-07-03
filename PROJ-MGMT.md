# FlowBoard AI-Powered Project Management System: Highly Extensive Technical & Feature Report

FlowBoard is an enterprise-grade project management application designed to integrate seamless task tracking, rich text documentation, and artificial intelligence directly into the project lifecycle. Built utilizing a modern web stack (Flask, Jinja2, Tailwind CSS, SQLite, and Scikit-Learn), it mimics functionality found in platforms like Jira and Notion, while augmenting user workflows with predictive machine learning.

This report comprehensively details the features, technical implementations, algorithms, and training methodologies of the system.

---

## 1. System Architecture & Core Stack

The application employs a modular architecture relying on the **MVC (Model-View-Controller)** pattern mapped through Flask Blueprints. This ensures high cohesion and low coupling across the codebase.
*   **Backend Framework**: Flask (Python) with highly modularized Blueprints (`auth`, `main`, `projects`, `tasks`, `organizations`, `docs`).
*   **Database Engine**: SQLite managed via SQLAlchemy ORM, ensuring ACID compliance and parameterized query safety.
*   **Frontend**: Jinja2 templating mapped with Tailwind CSS. The UI adheres to a Neo-Brutalism/Glassmorphism aesthetic without relying on heavy JS frameworks (using lightweight Alpine.js and Vanilla JS).
*   **Machine Learning**: Scikit-Learn pre-trained models injected via a unified Inference Engine (`app/services/ml_service.py`).
*   **Rich Text Editor**: Quill.js integration for tasks and comprehensive documentation.
*   **Drag-and-Drop Interactivity**: Sortable.js drives the Kanban board and sprint-planning UX.

### 1.1 Service Layer Pattern
To prevent business logic from bleeding into route handlers, the platform relies on service layers to encapsulate complex algorithms. For instance, the `MLService` class abstracts the entire model-loading and prediction pipeline, allowing routes (like `/tasks/ml/suggest`) to remain clean API endpoints.

---

## 2. Comprehensive Feature Analysis & Implementations

### 2.1 Multi-Tenant Organization Management
*   **Data Models**: The system supports multiple workspaces per user via the `Organization` and `Membership` models. 
*   **Implementation**: A global `@bp.before_app_request` middleware intercepts every request. If an authenticated user lacks an active workspace session (`active_org_id`), they are instantly redirected to create or join one. All project and task queries are inherently scoped to this active ID to prevent cross-tenant data leaks.

### 2.2 Advanced Project & Sprint Management
*   **Project Module**: Users can create overarching projects with defined metadata (Status, Priority, Lead, Start/End Dates).
*   **Sprint Lifecycle**: Sprints dictate the active development phases. They feature a `before_request` automated hook: If a sprint's `end_date` is surpassed and it is marked `is_active=True`, the backend automatically expires the sprint and demotes all incomplete tasks back to the core Backlog.
*   **Subtask Hierarchies**: Tasks support `parent_id` foreign keys, allowing infinite-depth subtasking logic. Parent tasks cascade their sprint assignments down to their subtasks automatically.

### 2.3 Interactive Kanban Board (Sortable.js)
*   **Implementation**: The `project_details.html` template uses Sortable.js to instantiate drag-and-drop zones for `To Do`, `In Progress`, and `Done` columns.
*   **Asynchronous Updates**: When a user drops a task card, a JavaScript `onEnd` event listener fires a non-blocking `fetch` POST request to `/tasks/<id>/update`. This silently updates the SQLite database with the new status, updates UI badges dynamically, and prevents the need for a full page reload, ensuring a buttery-smooth UX.

### 2.4 Notion-Style Documentation System
*   **Mechanism**: The Docs blueprint integrates `Quill.js` for WYSIWYG editing.
*   **Relationships**: Documents are fully relational. They can act as standalone project wikis or be directly linked to specific Tasks or Sprints via nullable foreign keys. Content is sanitized and stored as raw HTML strings in the database.

### 2.5 Audit Trails & Activity Logging
*   **Implementation**: A dedicated `ActivityLog` model captures every critical write operation (task creation, assignment, status change, deletion). 
*   **Utility**: The `log_activity()` helper function is triggered alongside `db.session.commit()` calls in the routes, providing a permanent, transparent audit trail for project managers.
*   **Notifications**: Handled by the `create_notification()` utility. Assigning a user to a task generates a targeted alert, updating their unread notification badge in real-time.

---

## 3. Artificial Intelligence & Machine Learning Integrations

FlowBoard fundamentally departs from traditional systems by natively injecting ML inference into the task and project creation workflows. This acts to standardize issue creation, predict timelines, and flag risks.

### 3.1 The Dataset & Training Process
The models were trained offline using a custom `train.py`/Jupyter Notebook pipeline located in `Machine_Learning/`.
*   **Dataset**: A synthetic dataset of 3,000 JIRA issues, combining textual descriptions (`title` + `description`), standard categories, priorities, and historically completed durations.
*   **EDA (Exploratory Data Analysis)**: The pipeline includes exhaustive feature correlation analysis, generating plots for duration distributions across priorities, text-length histograms, and cross-tabulations (e.g., verifying if "Bugs" correlate heavily with "Highest" priority).
*   **Artifacts**: The final trained models are serialized as Joblib (`.pkl`) files stored in the `Machine_Learning/models/` directory.

### 3.2 The ML Algorithms and Feature Engineering

The inference engine relies on three distinct predictive models initialized at startup.

#### Model 1: Task Category Classifier
*   **Objective**: Classifies the task into one of 8 standardized codebase classes (`Task`, `Feature`, `Bug`, `Design`, `Frontend`, `Backend`, `DevOps`, `Docs`).
*   **Algorithm**: **Logistic Regression** (L2 penalty, `C=1.0`, balanced class weight to handle minority classes like Docs/DevOps).
*   **Feature Extraction**: `TfidfVectorizer` (Term Frequency-Inverse Document Frequency). Limits vocabulary to the top 5,000 features using unigrams and bigrams (`ngram_range=(1,2)`). English stop words are stripped.
*   **Why Logistic Regression?**: Chosen for its high speed, low inference latency, and excellent baseline performance on sparse TF-IDF matrices compared to heavy deep learning models.

#### Model 2: Priority Classifier
*   **Objective**: Predicts the urgency of the task (`Low`, `Medium`, `High`, `Highest`).
*   **Algorithm**: **Random Forest Classifier**.
*   **Hyperparameters**: `n_estimators=150`, `max_depth=15`.
*   **Why Random Forest?**: Priority assignment often relies on complex, non-linear relationships of specific critical keywords (e.g., "fatal error", "outage", "production down"). Random Forest was chosen because it effectively captures these word combinations, is exceptionally robust against overfitting, and requires very little hyperparameter tuning compared to boosting models.

#### Model 3: Duration Predictor (Regression)
*   **Objective**: Predicts the estimated time to completion (in days).
*   **Algorithm**: **Random Forest Regressor**.
*   **Combined Feature Engineering**: This model does not just look at text. It concatenates the TF-IDF text matrix with the `LabelEncoded` numerical outputs of the *actual category and priority* of the task.
*   **Math Representation**: `hstack([tfidf_matrix, category_encoded, priority_encoded])` via Scipy Sparse matrices.
*   **Business Logic**: The raw regression output is rounded to an integer. Business rules enforce a minimum clamp depending on the context (`max(1, predicted)` for standard tasks, `max(10, predicted)` for macro-level projects). Random Forest Regressor provides excellent baseline performance and handles the highly sparse combined feature space extremely well.

### 3.3 Dynamic Template Generation & UI Integration
When the user clicks the AI "Sparkle" button in the UI, the frontend makes an asynchronous fetch call to `/ml/suggest`.
*   **Dynamic UI Sync**: The backend inference script evaluates the text, runs all three models sequentially, and injects the output back into the DOM.
*   **HTML Description Generation**: The ML Engine dynamically generates a structured HTML-formatted text based on the ML prediction variables. It injects the predicted values into an HTML template containing `<h4>` headers, `<p>` blocks, and `<ul>` lists for standardized QA/action items.
*   **Quill.js Bridge**: The generated HTML string is programmatically injected directly into the active `Quill.js` Rich Text Editor viewport via `window.quillTask.root.innerHTML = data.suggested_description`, creating a seamless "magic" auto-complete experience.

### 3.4 Risk Analytics & Project Dashboards
The platform features a dedicated analytics tab rendered utilizing `Chart.js`.
1.  **Status Distribution**: A pie chart evaluating the raw numerical distribution of `To Do`, `In Progress`, and `Done` states.
2.  **Classification Allocation**: A dynamic bar graph that groups tasks strictly by their `issue_type` parameters, allowing project managers to visualize whether the sprint is disproportionately loaded with "Bugs" versus "Features" (Technical Debt analysis).
3.  **Risk Detection**: Simulated endpoint evaluation checking the ratio of overdue tasks against sprint timeline constraints and AI duration estimations to output a project "Health Score".
