from flask import render_template, redirect, url_for, request, jsonify, flash
from flask_login import login_required, current_user
from app.tasks import bp
from app.models import Project, Task, Sprint, Comment, Membership
from app.extensions import db
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from app.services.ml_service import MLService
from app.utils.notifications import create_notification
from app.utils.activity import log_activity
from app.utils.rbac import requires_project_manager

@bp.before_app_request
def auto_move_overdue_tasks():
    if current_user and current_user.is_authenticated:
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

        # 2. Find all top-level tasks (not subtasks) that are:
        # 1. Not in 'Done' status
        # 2. Have a due date set
        # 3. Due date is in the past (before now)
        # 4. Currently assigned to a sprint (sprint_id is not None)
        # and automatically move them to the backlog (sprint_id = None)
        # Subtasks are excluded since they inherit sprint from their parent.
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
                # Also move subtasks to backlog
                for subtask in task.subtasks:
                    subtask.sprint_id = None
            db.session.commit()

@bp.route('/<int:task_id>')
@login_required
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    # Get organization members for assignee dropdown in detail panel
    project = task.project
    org_members = [m.user for m in Membership.query.filter_by(organization_id=project.organization_id).all()]
    return render_template('tasks/task_snippet.html', task=task, org_members=org_members, Comment=Comment)

@bp.route('/create', methods=['POST'])
@login_required
def create_task():
    title = request.form.get('title')
    description = request.form.get('description', '')
    project_id = request.form.get('project_id')
    issue_type = request.form.get('issue_type', 'Task')
    priority = request.form.get('priority', 'Medium')
    
    assignee_id_str = request.form.get('assignee_id')
    assignee_id = int(assignee_id_str) if assignee_id_str and assignee_id_str.isdigit() else None
    
    due_date_str = request.form.get('due_date')
    status = request.form.get('status', 'To Do')
    
    sprint_id_str = request.form.get('sprint_id')
    sprint_id = int(sprint_id_str) if sprint_id_str and sprint_id_str.isdigit() else None
    
    if not title or not project_id:
        return redirect(request.referrer)
        
    # Trigger ML Inference
    text_for_ml = f"{title} {description}"
    prediction = MLService.suggest_for_task(text_for_ml)
    
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            pass

    # Validate against project dates
    project = Project.query.get(project_id)
    if project and project.end_date and due_date:
        if due_date > project.end_date:
            flash(f"Task due date cannot exceed project end date ({project.end_date.strftime('%Y-%m-%d')}).", 'error')
            return redirect(request.referrer)

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
    db.session.commit()
    
    if assignee_id and assignee_id != current_user.id:
        create_notification(
            user_id=assignee_id,
            title="New Task Assigned",
            message=f"You have been assigned to task: {title}",
            type="info",
            link=url_for('projects.project_details', project_id=project_id) + '?tab=board'
        )
        
    log_activity(f"Created task: {title}", project_id, task.id)
    flash('Task created!', 'success')
    return redirect(request.referrer)

@bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete_tasks():
    data = request.get_json()
    task_ids = [int(tid) for tid in data.get('task_ids', []) if str(tid).isdigit()]
    
    if not task_ids:
        return jsonify({'success': False, 'message': 'No valid task IDs provided'}), 400
        
    tasks_to_delete = Task.query.filter(Task.id.in_(task_ids)).all()
    project_id = tasks_to_delete[0].project_id if tasks_to_delete else None
    for task in tasks_to_delete:
        db.session.delete(task)
        
    db.session.commit()
    if project_id:
        log_activity(f"Batch deleted {len(tasks_to_delete)} tasks", project_id)
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
    db.session.commit()
    log_activity(f"Deleted task: {title}", project_id)
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
        
    if hasattr(task, field):
        if field == 'due_date' and value:
            try:
                parsed_date = datetime.strptime(value, '%Y-%m-%d')
                if task.project.end_date and parsed_date > task.project.end_date:
                    return jsonify({'success': False, 'message': f"Due date cannot exceed project end date ({task.project.end_date.strftime('%Y-%m-%d')})."}), 400
                value = parsed_date
            except ValueError:
                return jsonify({'success': False, 'message': 'Invalid date format'}), 400
        elif field == 'assignee_id':
            value = int(value) if value and str(value).isdigit() else None
            
        setattr(task, field, value)
        db.session.commit()
        
        log_activity(f"Updated task {field} to {value}", task.project_id, task.id)
        
        if field == 'assignee_id' and value and value != current_user.id:
            create_notification(
                user_id=value,
                title="Task Assigned",
                message=f"You have been assigned to task: {task.title}",
                type="info",
                link=url_for('projects.project_details', project_id=task.project_id) + '?tab=board'
            )
            
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'message': f'Invalid field: {field}'}), 400

@bp.route('/ml/suggest', methods=['POST'])
@login_required
def ml_suggest():
    from app.services.ml_service import MLService
    from datetime import timedelta

    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    if not title:
        return jsonify({'success': False, 'message': 'No title provided'}), 400

    prediction = MLService.suggest_for_task(title, description)
    suggested_date = (datetime.utcnow() + timedelta(days=prediction['duration_days'])).strftime('%Y-%m-%d')

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
def create_subtask(task_id):
    parent = Task.query.get_or_404(task_id)
    data = request.get_json()
    title = data.get('title', '').strip()
    due_date_str = data.get('due_date', '').strip() if data.get('due_date') else ''
    
    if not title:
        return jsonify({'success': False, 'message': 'Title is required'}), 400
    
    # Parse and validate due_date against parent's due_date
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
        
        if parent.due_date and due_date > parent.due_date:
            return jsonify({
                'success': False, 
                'message': f"Subtask due date cannot exceed parent task's due date ({parent.due_date.strftime('%Y-%m-%d')})."
            }), 400
    
    # Run ML prediction for subtask classification
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
        due_date=due_date,
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
    content = request.form.get('content')
    if content:
        from app.models import Comment
        comment = Comment(content=content, task_id=task.id, user_id=current_user.id)
        db.session.add(comment)
        db.session.commit()
        log_activity(f"Commented on task: {task.title}", task.project_id, task.id)
    return redirect(request.referrer)

@bp.route('/<int:task_id>/attach', methods=['POST'])
@login_required
def attach_file(task_id):
    from flask import current_app
    from werkzeug.utils import secure_filename
    from app.models import Attachment
    import os
    
    task = Task.query.get_or_404(task_id)
    file = request.files.get('file')
    
    if file and file.filename:
        filename = secure_filename(file.filename)
        # Create uploads folder if not exists
        upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'attachments')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
            
        file.save(os.path.join(upload_path, filename))
        
        attachment = Attachment(
            filename=file.filename,
            file_path=f"uploads/attachments/{filename}",
            task_id=task.id,
            project_id=task.project_id,
            uploaded_by_id=current_user.id
        )
        db.session.add(attachment)
        db.session.commit()
        log_activity(f"Attached file {filename} to task: {task.title}", task.project_id, task.id)
        flash('File attached successfully', 'success')
        
    return redirect(request.referrer)
