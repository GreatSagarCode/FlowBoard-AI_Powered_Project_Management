"""Task routes — CRUD, comments, attachments, subtasks, ML suggestions, activity log."""
from flask import render_template, redirect, url_for, request, jsonify, flash, session
from flask_login import login_required, current_user
from app.tasks import bp
from app.models import Project, Task, Comment, Membership, Attachment, ActivityLog, User, Sprint
from app.extensions import db
from datetime import datetime
from app.services.ml_service import MLService
from app.utils.notifications import create_notification
from app.utils.activity import log_activity
from app.utils.rbac import requires_project_manager
from app.utils import get_membership


def _verify_org_access(organization_id):
    active_org_id = session.get('active_org_id')
    if organization_id != active_org_id:
        return False
    return get_membership() is not None


@bp.route('/<int:task_id>')
@login_required
def get_task(task_id):
    from sqlalchemy.orm import joinedload
    task = Task.query.options(
        joinedload(Task.attachments),
        joinedload(Task.subtasks),
        joinedload(Task.activity_logs)
    ).get_or_404(task_id)
    project = task.project
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        return "Access denied", 403
    if not get_membership():
        return "Access denied", 403
    import time
    org_members = [m.user for m in Membership.query.filter_by(organization_id=project.organization_id).all()]
    return render_template('tasks/task_snippet.html', task=task, org_members=org_members, Comment=Comment, cache_buster=int(time.time()))

@bp.route('/create', methods=['POST'])
@login_required
@requires_project_manager
def create_task():
    title = request.form.get('title', '').strip()[:150]
    description_raw = request.form.get('description', '').strip()[:5000]
    import bleach
    description = bleach.clean(description_raw, tags=['h1', 'h2', 'h3', 'p', 'br', 'strong', 'em', 'u', 's', 'blockquote', 'pre', 'ol', 'ul', 'li', 'a', 'img', 'span'], attributes={'*': ['class', 'style'], 'a': ['href', 'target'], 'img': ['src', 'alt']}, styles=['color', 'background-color']) if description_raw else ''
    project_id = request.form.get('project_id')
    issue_type = request.form.get('issue_type', 'Task')
    ALLOWED_ISSUE_TYPES = {'Task', 'Feature', 'Bug', 'Design', 'Frontend', 'Backend', 'DevOps', 'Docs', 'Subtask'}
    if issue_type not in ALLOWED_ISSUE_TYPES:
        issue_type = 'Task'
    priority = request.form.get('priority', 'Medium')
    ALLOWED_PRIORITIES = {'Low', 'Medium', 'High', 'Critical'}
    if priority not in ALLOWED_PRIORITIES:
        priority = 'Medium'
    
    assignee_id_str = request.form.get('assignee_id')
    assignee_id = int(assignee_id_str) if assignee_id_str and assignee_id_str.isdigit() else None
    
    due_date_str = request.form.get('due_date')
    status = request.form.get('status', 'To Do')
    
    sprint_id_str = request.form.get('sprint_id')
    sprint_id = int(sprint_id_str) if sprint_id_str and sprint_id_str.isdigit() else None

    if not title or not project_id:
        return redirect(url_for('projects.project_details', project_id=project_id) if project_id else url_for('projects.list_projects'))

    if not description:
        flash('Description is required.', 'error')
        return redirect(url_for('projects.project_details', project_id=project_id) if project_id else url_for('projects.list_projects'))

    project = Project.query.get(project_id)
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('projects.list_projects'))

    if assignee_id is not None:
        user = User.query.get(assignee_id)
        if not user or user not in project.members:
            flash('Assignee must be a member of this project.', 'error')
            return redirect(url_for('projects.project_details', project_id=project_id))

    if sprint_id is not None:
        sprint = Sprint.query.get(sprint_id)
        if not sprint or sprint.project_id != project.id:
            flash('Selected sprint does not belong to this project.', 'error')
            return redirect(url_for('projects.project_details', project_id=project_id))

    text_for_ml = f"{title} {description}"
    prediction = MLService.suggest_for_task(text_for_ml)

    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            pass

    if project.end_date and due_date:
        if due_date > project.end_date:
            flash(f"Task due date cannot exceed project end date ({project.end_date.strftime('%Y-%m-%d')}).", 'error')
            return redirect(url_for('projects.project_details', project_id=project_id))

    task = Task(
        title=title,
        description=description,
        project_id=project_id,
        sprint_id=sprint_id,
        issue_type=issue_type,
        priority=priority,
        category=prediction['category'],
        duration_days=prediction['duration_days'],
        assignee_id=assignee_id,
        due_date=due_date,
        status=status
    )
    
    db.session.add(task)
    
    if assignee_id and assignee_id != current_user.id:
        create_notification(
            user_id=assignee_id, organization_id=project.organization_id,
            title="New Task Assigned",
            message=f"You have been assigned to task: {title}",
            type="info",
            link=url_for('projects.project_details', project_id=project_id) + '?tab=board'
        )
        
    log_activity(f"Created task: {title}", project_id, task.id)
    db.session.commit()
    flash('Task created!', 'success')
    return redirect(url_for('projects.project_details', project_id=project_id))

@bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete_tasks():
    data = request.get_json()
    task_ids = [int(tid) for tid in data.get('task_ids', []) if str(tid).isdigit()]
    
    if not task_ids:
        return jsonify({'success': False, 'message': 'No valid task IDs provided'}), 400
    
    tasks_to_delete = Task.query.filter(Task.id.in_(task_ids)).all()
    if not tasks_to_delete:
        return jsonify({'success': False, 'message': 'No tasks found'}), 404

    project = tasks_to_delete[0].project
    is_manager = project.lead_id == current_user.id or project.created_by_id == current_user.id
    if not is_manager:
        org_membership = get_membership(project.organization_id)
        if not org_membership or org_membership.role != 'ADMIN':
            return jsonify({'success': False, 'message': 'Access denied. Manager role required.'}), 403
    
    for task in tasks_to_delete:
        db.session.delete(task)
        
    log_activity(f"Batch deleted {len(tasks_to_delete)} tasks", project.id)
    db.session.commit()
    flash(f'{len(tasks_to_delete)} tasks deleted successfully.', 'success')
    return jsonify({'success': True})

@bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
@requires_project_manager
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    project_id = task.project_id
    title = task.title
    db.session.delete(task)
    log_activity(f"Deleted task: {title}", project_id)
    db.session.commit()
    flash('Task deleted.', 'success')
    return jsonify({'success': True})

@bp.route('/<int:task_id>/update', methods=['POST'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    
    if not field:
        return jsonify({'success': False, 'message': 'No field provided'}), 400
        
    project = task.project
    is_manager = project.lead_id == current_user.id or project.created_by_id == current_user.id
    if not is_manager:
        m = get_membership(project.organization_id)
        is_manager = m and m.role == 'ADMIN'

    if not is_manager and field != 'status':
        return jsonify({'success': False, 'message': 'Access denied. You can only update the status.'}), 403

    if field == 'status':
        m = get_membership(task.project.organization_id)
        if m and m.role == 'CONTRIBUTOR' and task.assignee_id != current_user.id:
            return jsonify({'success': False, 'message': 'Contributors can only update status on their own tasks.'}), 403

    if field == 'status' and value == 'Done' and task.subtasks:
        if any(st.status != 'Done' for st in task.subtasks):
            return jsonify({'success': False, 'message': 'All subtasks must be completed first.'}), 400
    
    ALLOWED_FIELDS = ['status', 'priority', 'assignee_id', 'due_date', 'title', 'description', 'issue_type', 'category', 'duration_days', 'story_points']
    if field not in ALLOWED_FIELDS:
        return jsonify({'success': False, 'message': 'Field not allowed'}), 400

    if hasattr(task, field):
        if field == 'due_date' and value:
            try:
                parsed_date = datetime.strptime(value, '%Y-%m-%d')
                if task.project.end_date and parsed_date > task.project.end_date:
                    return jsonify({'success': False, 'message': f"Due date cannot exceed project end date ({task.project.end_date.strftime('%Y-%m-%d')})."}), 400
                # If this task is a subtask, validate against parent's due date
                if task.parent and task.parent.due_date and parsed_date > task.parent.due_date:
                    return jsonify({
                        'success': False,
                        'message': f"Subtask due date cannot exceed parent task's due date ({task.parent.due_date.strftime('%Y-%m-%d')})."
                    }), 400
                value = parsed_date
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid date format'}), 400
        elif field == 'assignee_id':
            value = int(value) if value and str(value).isdigit() else None
            if value is not None:
                user = User.query.get(value)
                if not user or user not in project.members:
                    return jsonify({'success': False, 'message': 'Assignee must be a member of this project.'}), 400
        elif field == 'story_points':
            if not value and value != 0:
                value = None
            else:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Story points must be a whole number.'}), 400
        elif field == 'duration_days':
            if not value and value != 0:
                value = None
            else:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': 'Duration must be a number.'}), 400
                if task.project.end_date and task.project.start_date:
                    project_days = (task.project.end_date - task.project.start_date).days
                    if value > project_days:
                        return jsonify({'success': False, 'message': f'Duration cannot exceed project duration ({project_days} days).'}), 400
            
        setattr(task, field, value)
        db.session.commit()
        
        adjusted_subtasks = []
        if field == 'due_date' and task.subtasks:
            for subtask in task.subtasks:
                if value and subtask.due_date and subtask.due_date > value:
                    subtask.due_date = value
                    adjusted_subtasks.append(subtask.title)
            if adjusted_subtasks:
                db.session.commit()
                log_activity(f"Auto-adjusted {len(adjusted_subtasks)} subtask(s) to match parent due date", task.project_id, task.id)
        
        if field == 'status':
            from app.extensions import socketio
            socketio.emit('task_moved', {
                'task_id': task.id,
                'status': value,
                'project_id': task.project_id,
                'updated_by': current_user.id
            }, room=f'project_{task.project_id}')
        
        log_activity(f"Updated task {field} to {value}", task.project_id, task.id)
        
        if field == 'assignee_id' and value and value != current_user.id:
            create_notification(
                user_id=value, organization_id=task.project.organization_id,
                title="Task Assigned",
                message=f"You have been assigned to task: {task.title}",
                type="info",
                link=url_for('projects.project_details', project_id=task.project_id) + '?tab=board'
            )
        
        db.session.commit()
        
        response = {'success': True}
        if adjusted_subtasks:
            response['warning'] = f"Due dates for {len(adjusted_subtasks)} subtask(s) were adjusted to match the new parent due date: {', '.join(adjusted_subtasks)}"
        return jsonify(response)
        
    return jsonify({'success': False, 'message': f'Invalid field: {field}'}), 400

@bp.route('/ml/suggest', methods=['POST'])
@login_required
def ml_suggest():
    from app.services.ml_service import MLService
    from datetime import timedelta

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Invalid JSON body'}), 400
    title = data.get('title', '')
    description = data.get('description', '')
    if not isinstance(title, str) or not isinstance(description, str):
        return jsonify({'success': False, 'message': 'Title and description must be strings'}), 400
    title = title.strip()
    description = description.strip()
    if not title:
        return jsonify({'success': False, 'message': 'No title provided'}), 400

    try:
        prediction = MLService.suggest_for_task(title, description)
        suggested_date = (datetime.utcnow() + timedelta(days=prediction['duration_days'])).strftime('%Y-%m-%d')
    except Exception:
        return jsonify({
            'success': True,
            'category': 'Task',
            'duration_days': 10,
            'priority': 'Medium',
            'suggested_description': 'Please provide more details.',
            'suggested_date': (datetime.utcnow() + timedelta(days=10)).strftime('%Y-%m-%d'),
        })

    return jsonify({
        'success': True,
        'category': prediction.get('category', ''),
        'duration_days': prediction.get('duration_days', 0),
        'priority': prediction.get('priority', 'Medium'),
        'suggested_description': prediction.get('suggested_description', ''),
        'suggested_date': suggested_date,
    })

@bp.route('/<int:task_id>/subtask', methods=['POST'])
@login_required
@requires_project_manager
def create_subtask(task_id):
    parent = Task.query.get_or_404(task_id)
    data = request.get_json()
    title = data.get('title', '').strip()
    due_date_str = data.get('due_date', '').strip() if data.get('due_date') else ''
    
    if not title:
        return jsonify({'success': False, 'message': 'Title is required'}), 400

    p = parent
    depth = 0
    while p.parent_id is not None:
        depth += 1
        p = p.parent
        if depth >= 2:
            return jsonify({'success': False, 'message': 'Maximum nesting depth (3 levels) exceeded.'}), 400

    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
        if parent.due_date and due_date > parent.due_date:
            return jsonify({'success': False, 'message': f"Subtask due date cannot exceed parent's due date ({parent.due_date.strftime('%Y-%m-%d')})."}), 400

    text_for_ml = f"{title}"
    prediction = MLService.suggest_for_task(text_for_ml)
    
    subtask = Task(
        title=title,
        description='',
        project_id=parent.project_id,
        sprint_id=parent.sprint_id,
        parent_id=parent.id,
        issue_type='Subtask',
        status='To Do',
        due_date=due_date or parent.due_date,
        assignee_id=parent.assignee_id,
        category=prediction['category'],
        duration_days=prediction['duration_days']
    )
    
    db.session.add(subtask)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/<int:task_id>/comment', methods=['POST'])
@login_required
def add_comment(task_id):
    task = Task.query.get_or_404(task_id)
    project = task.project
    from flask import session
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return "Access denied", 403
    content = request.form.get('content', '').strip()[:2000]
    if not content:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Comment cannot be empty.'}), 400
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('projects.project_details', project_id=task.project_id) + '?tab=board')
    comment = Comment(content=content, task_id=task.id, user_id=current_user.id)
    db.session.add(comment)
    log_activity(f"Commented on task: {task.title}", task.project_id, task.id)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Comment posted successfully'})
    return redirect(url_for('projects.project_details', project_id=task.project_id) + '?tab=board')

@bp.route('/<int:task_id>/attach', methods=['POST'])
@login_required
def attach_file(task_id):
    from werkzeug.utils import secure_filename
    import os

    task = Task.query.get_or_404(task_id)
    if task.project.organization_id != session.get('active_org_id'):
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    m = get_membership(task.project.organization_id)
    if not m:
        return jsonify({'success': False, 'message': 'Access denied. Not a member.'}), 403
    if m.role == 'CONTRIBUTOR':
        return jsonify({'success': False, 'message': 'Contributors cannot upload files.'}), 403

    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'csv', 'txt', 'zip', 'xls', 'xlsx'}
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'success': False, 'message': f'File type not allowed: {ext}'}), 400

    file_data = file.read()
    if len(file_data) > 10 * 1024 * 1024:
        return jsonify({'success': False, 'message': 'File too large. Maximum size is 10MB.'}), 400
    file.seek(0)

    filename = secure_filename(file.filename)
    upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'attachments')
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    try:
        file.save(os.path.join(upload_path, filename))
        attachment = Attachment(
            filename=file.filename, file_path=f"uploads/attachments/{filename}",
            task_id=task.id, project_id=task.project_id, uploaded_by_id=current_user.id
        )
        db.session.add(attachment)
        log_activity(f"Attached file {filename} to task: {task.title}", task.project_id, task.id)
        db.session.commit()
        return jsonify({
            'success': True, 'message': 'File attached successfully',
            'attachment': {
                'id': attachment.id, 'filename': attachment.filename,
                'file_url': url_for('static', filename=attachment.file_path),
                'uploaded_by': current_user.username
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Failed to save attachment: {str(e)}'}), 500

@bp.route('/attachment/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    from flask import current_app, session
    from app.models import Attachment
    import os

    attachment = Attachment.query.get_or_404(attachment_id)
    task_id = attachment.task_id
    task = Task.query.get_or_404(task_id)
    
    active_org_id = session.get('active_org_id')
    if task.project.organization_id != active_org_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    project = task.project
    membership = get_membership(project.organization_id)

    can_delete = False
    if membership and membership.role == 'ADMIN':
        can_delete = True
    elif project.lead_id == current_user.id or project.created_by_id == current_user.id:
        can_delete = True
    elif attachment.uploaded_by_id == current_user.id:
        can_delete = True

    if not can_delete:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'You can only delete your own attachments.'}), 403
        flash('You can only delete your own attachments.', 'error')
        return redirect(url_for('projects.project_details', project_id=task.project_id) + '?tab=board')

    try:
        file_path = os.path.join(current_app.root_path, 'static', attachment.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error deleting file: {e}")

    db.session.delete(attachment)
    log_activity(f"Deleted attachment {attachment.filename} from task: {task.title}", task.project_id, task.id)
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Attachment deleted successfully'})

    flash('Attachment deleted successfully', 'success')
    return redirect(url_for('projects.project_details', project_id=task.project_id) + '?tab=board')

def _is_org_admin(organization_id):
    membership = get_membership(organization_id)
    return membership is not None and membership.role == 'ADMIN'

@bp.route('/comment/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    task = Task.query.get_or_404(comment.task_id)
    project = task.project
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    if not _is_org_admin(project.organization_id) and comment.user_id != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Only admins can delete others comments'}), 403
        flash('Only admins can delete others comments.', 'error')
        return redirect(url_for('main.index'))
    db.session.delete(comment)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Comment deleted successfully'})
    flash('Comment deleted successfully', 'success')
    return redirect(url_for('projects.project_details', project_id=task.project_id) + '?tab=board')

@bp.route('/<int:task_id>/comments', methods=['DELETE'])
@login_required
def clear_comments(task_id):
    task = Task.query.get_or_404(task_id)
    project = task.project
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    if not _is_org_admin(project.organization_id):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Only admins can clear all comments'}), 403
        flash('Only admins can clear all comments.', 'error')
        return redirect(url_for('main.index'))
    Comment.query.filter_by(task_id=task.id).delete()
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'All comments cleared'})
    flash('All comments cleared', 'success')
    return redirect(url_for('projects.project_details', project_id=task.project_id) + '?tab=board')

@bp.route('/activity/<int:activity_id>', methods=['DELETE'])
@login_required
def delete_activity(activity_id):
    activity = ActivityLog.query.get_or_404(activity_id)
    if activity.task_id is None:
        return jsonify({'success': False, 'message': 'Activity has no linked task.'}), 400
    task = Task.query.get_or_404(activity.task_id)
    project = task.project
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    if not _is_org_admin(project.organization_id):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Only admins can delete activity entries'}), 403
        flash('Only admins can delete activity entries.', 'error')
        return redirect(url_for('main.index'))
    db.session.delete(activity)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Activity deleted successfully'})
    flash('Activity deleted successfully', 'success')
    return redirect(url_for('projects.project_details', project_id=task.project_id) + '?tab=board')

@bp.route('/<int:task_id>/activity', methods=['DELETE'])
@login_required
def clear_activity(task_id):
    task = Task.query.get_or_404(task_id)
    project = task.project
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    if not _is_org_admin(project.organization_id):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Only admins can clear activity history'}), 403
        flash('Only admins can clear activity history.', 'error')
        return redirect(url_for('main.index'))
    ActivityLog.query.filter_by(task_id=task.id).delete()
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Activity history cleared'})
    flash('Activity history cleared', 'success')
    return redirect(url_for('projects.project_details', project_id=task.project_id) + '?tab=board')
