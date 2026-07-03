from app.extensions import db
from app.models import Notification

def create_notification(user_id, title, message, type='info', link=None):
    """
    Creates a new notification for a specific user and commits it to the database.
    """
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link
        )
        db.session.add(notification)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error creating notification: {e}")
        db.session.rollback()
        return False
