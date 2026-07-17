from app.extensions import db
from app.models import Sprint, Task
from datetime import datetime

def run_maintenance_job(app):
    with app.app_context():
        # 1. Expire Active Sprints that passed their end date
        expired_sprints = Sprint.query.filter(
            Sprint.is_active == True,
            Sprint.end_date != None,
            Sprint.end_date < datetime.utcnow()
        ).all()
        
        for sprint in expired_sprints:
            sprint.is_active = False
            # Move incomplete tasks back to backlog
            incomplete_tasks = sprint.tasks.filter(Task.status != 'Done').all()
            for task in incomplete_tasks:
                task.sprint_id = None
                for subtask in task.subtasks:
                    subtask.sprint_id = None
        db.session.commit()

        # 2. Find all overdue top-level tasks and move them to backlog
        overdue_tasks = Task.query.filter(
            Task.status != 'Done',
            Task.due_date != None,
            Task.due_date < datetime.utcnow(),
            Task.sprint_id != None,
            Task.parent_id == None
        ).all()
        
        if overdue_tasks:
            for task in overdue_tasks:
                task.sprint_id = None
                for subtask in task.subtasks:
                    subtask.sprint_id = None
            db.session.commit()
