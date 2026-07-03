from app.models import ActivityLog
from app.extensions import db
from flask_login import current_user

def log_activity(action, project_id, task_id=None):
    if not current_user or not current_user.is_authenticated:
        return
        
    log = ActivityLog(
        action=action,
        user_id=current_user.id,
        project_id=project_id,
        task_id=task_id
    )
    db.session.add(log)
    db.session.commit()
