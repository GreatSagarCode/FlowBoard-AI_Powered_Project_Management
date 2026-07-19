"""Activity logging utility — logs user actions to the ActivityLog table."""
from app.models import ActivityLog, Project
from app.extensions import db
from flask_login import current_user

def log_activity(action, project_id, task_id=None, organization_id=None):
    if not current_user or not current_user.is_authenticated:
        return

    if not organization_id:
        project = Project.query.with_entities(Project.organization_id).filter_by(id=project_id).first()
        organization_id = project.organization_id if project else None

    log = ActivityLog(
        action=action,
        user_id=current_user.id,
        project_id=project_id,
        task_id=task_id,
        organization_id=organization_id
    )
    db.session.add(log)
