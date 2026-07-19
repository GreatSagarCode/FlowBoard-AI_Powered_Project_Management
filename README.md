# FlowBoard — AI-Powered Project Management

FlowBoard is a project management tool with AI-powered task suggestions, real-time collaboration via WebSockets, and a kanban-style task board.

## Tech Stack

- **Backend**: Python, Flask, SQLAlchemy, Flask-SocketIO
- **Frontend**: Tailwind CSS, Alpine.js, Quill.js, Chart.js, Lucide Icons
- **ML**: scikit-learn (TF-IDF + Logistic Regression for task categorization)
- **Database**: SQLite (default), PostgreSQL-ready

## Features

- Workspace/Organization management with role-based access (Admin, Member, Contributor)
- Project management with kanban boards and sprint planning
- Task management with drag-and-drop, subtasks, attachments, and comments
- AI-powered task categorization, duration estimation, and description suggestions
- Real-time updates via WebSockets (task moves, notifications)
- Rich text editor (Quill) for task descriptions and documents
- Team management with invitations and role assignment
- Global search across projects and tasks
- Dark mode support

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd FlowBoard

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your SECRET_KEY

# Run the app
python wsgi.py
```

The app will be available at `http://localhost:5000`. Register a new account to get started.

## Project Structure

```
app/
  auth/          # Authentication routes (login, register)
  main/          # Dashboard, team, settings, profile
  projects/      # Project CRUD, sprints, file attachments
  tasks/         # Task CRUD, comments, attachments, ML suggestions
  organizations/ # Workspace creation, invitations
  docs/          # Document creation and editing
  ml/            # ML model training and inference
  utils/         # RBAC decorator, activity logging, notifications
  static/        # JS, uploads
  templates/     # Jinja2 HTML templates
```

## Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full workspace control — manage projects, tasks, team, settings |
| **Member** (is project lead) | Manage assigned project — tasks, sprints, docs, team members |
| **Member** | View projects, update task status, comment, upload files |
| **Contributor** | View projects, comment on own tasks, update own task status |

