"""WebSocket event handlers — board join/leave and global notifications."""
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio
from flask_login import current_user
from app.models import Project, Membership

@socketio.on('join_board')
def on_join(data):
    project_id = data.get('project_id')
    if not project_id or not current_user.is_authenticated:
        return
    project = Project.query.get(project_id)
    if not project:
        return
    membership = Membership.query.filter_by(user_id=current_user.id, organization_id=project.organization_id).first()
    if not membership:
        return
    room = f'project_{project_id}'
    join_room(room)

@socketio.on('leave_board')
def on_leave(data):
    project_id = data.get('project_id')
    if project_id:
        room = f'project_{project_id}'
        leave_room(room)

@socketio.on('join_global')
def on_join_global(data):
    if current_user.is_authenticated:
        room = f'user_{current_user.id}'
        join_room(room)
