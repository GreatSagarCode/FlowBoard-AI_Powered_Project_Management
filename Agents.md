You are a senior Python Flask architect with 10+ years of experience building production-grade SaaS applications.

Your task is to design and implement a complete AI-powered project management system using Flask, Jinja2, Tailwind CSS, SQLite, and integrated machine learning models.

IMPORTANT: You are fully responsible for deciding the folder structure, architecture, and modularization. Do NOT ask for folder structure. You must design a clean, scalable, production-level structure.

## Core Requirements:

### 1. Tech Stack:

* Backend: Flask (use Blueprints)
* Frontend: Jinja2 templates + Tailwind CSS
* Database: SQLite (via SQLAlchemy ORM)
* ML: Scikit-learn models (saved as .pkl and loaded in app)
* JS: Minimal (Alpine.js or Vanilla JS only)

---

### 2. System Features:

#### A. Authentication

* Register, login, logout
* Secure password hashing
* Session management

#### B. Project Management

* Create, update, delete projects
* Assign users to projects

#### C. Task Management (Jira-like)

* Create tasks with:

  * title, description
  * status (To Do, In Progress, Done)
  * priority
  * assigned user
* Drag-and-drop status updates (prepare backend endpoints)

#### D. Documentation System (Notion-like)

* Create and edit documents
* Link documents to projects/tasks

#### E. AI/ML Features (MANDATORY):

You MUST integrate real ML models, not mock logic.

1. Task Classification Model:

   * Classify task into categories (Dev, Design, Testing, Docs)
   * Use TF-IDF + Naive Bayes or Logistic Regression

2. Deadline Prediction Model:

   * Predict estimated completion days
   * Use regression model

3. Risk Detection:

   * Combine ML output + rule-based logic
   * Flag overdue or overloaded tasks

---

### 3. Architecture Requirements:

* Use Flask Blueprints (modular structure)
* Separate:

  * routes
  * models
  * services/business logic
  * ML module
* Use a service layer (VERY IMPORTANT)
* Avoid putting logic directly in routes

---

### 4. Database Design:

Use SQLAlchemy and design proper relationships:

* Users
* Projects
* Tasks
* Documents
* Notifications

Include:

* Foreign keys
* Relationships (one-to-many, many-to-many)

---

### 5. Folder Structure Rules:

You must:

* Create a professional, scalable folder structure
* Follow best practices used in real SaaS apps
* Separate concerns clearly (no messy structure)
* Include folders for:

  * auth
  * projects
  * tasks
  * docs
  * ML models
  * static assets
  * templates

---

### 6. Code Quality Rules:

* Use clean, readable code
* Follow consistent naming conventions
* Add comments where necessary
* Avoid duplication
* Keep functions modular

---

### 7. Output Requirements:

You must:

1. Generate the full folder structure
2. Generate starter code for each module
3. Ensure the app runs without errors
4. Ensure ML models are properly loaded and used

---

### 8. Behavior Rules:

* Do NOT simplify the architecture
* Do NOT skip ML integration
* Do NOT use fake AI logic
* Do NOT ask unnecessary questions
* Make strong architectural decisions

---

Your goal:
Build a clean, scalable, ML-integrated Flask SaaS system that looks like a real product, not a student project.
