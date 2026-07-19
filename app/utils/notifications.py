"""Notification utility — creates in-app notifications and emits real-time alerts via WebSocket."""
from app.extensions import db
from app.models import Notification

def create_notification(user_id, title, message, type='info', link=None, organization_id=None):
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link,
            organization_id=organization_id
        )
        db.session.add(notification)

        from app.extensions import socketio
        socketio.emit('new_notification', {
            'title': title,
            'message': message,
            'type': type,
            'link': link
        }, room=f"user_{user_id}")

        return True
    except Exception as e:
        print(f"Error creating notification: {e}")
        return False
