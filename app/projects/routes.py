from flask import render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from app.projects import bp
from app.models import Project, Sprint, Task, Document, Organization, Membership, User
from app.extensions import db
from datetime import datetime
from app.utils.notifications import create_notification
from app.utils.rbac import requires_project_manager

@bp.route('/')
@login_required
def list_projects():
    active_org_id = session.get('active_org_id')
    page = request.args.get('page', 1, type=int)
    projects_pagination = Project.query.filter_by(organization_id=active_org_id).order_by(Project.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    projects = projects_pagination.items
    org_members = [m.user for m in Membership.query.filter_by(organization_id=active_org_id).all()]
    org = Organization.query.get(active_org_id)
    membership = Membership.query.filter_by(user_id=current_user.id, organization_id=active_org_id).first()
    is_admin = membership and membership.role == 'ADMIN'
    return render_template('projects/list.html', projects=projects, pagination=projects_pagination, org_members=org_members, org=org, is_admin=is_admin)

@bp.route('/create', methods=['POST'])
@login_required
def create_project():
    title = request.form.get('title', '').strip()[:100]
    description = request.form.get('description', '').strip()[:2000]
    active_org_id = session.get('active_org_id')
    status = request.form.get('status', '').strip()
    priority = request.form.get('priority', '').strip()
    lead_id = request.form.get('lead_id', '').strip()
    start_date_raw = request.form.get('start_date', '').strip()
    end_date_raw = request.form.get('end_date', '').strip()
    member_ids = request.form.getlist('member_ids')

    if not (title and description and status and priority and start_date_raw and end_date_raw and lead_id and member_ids):
        flash('All fields are required to create a project, including at least one team member.', 'error')
        return redirect(url_for('projects.list_projects'))

    from datetime import datetime, timedelta
    lead_id = int(lead_id)

    try:
        start_date = datetime.strptime(start_date_raw, '%Y-%m-%d')
    except ValueError:
        start_date = datetime.utcnow()

    try:
        end_date = datetime.strptime(end_date_raw, '%Y-%m-%d')
    except ValueError:
        end_date = start_date + timedelta(days=30)

    project = Project(
        title=title,
        description=description,
        organization_id=active_org_id,
        created_by_id=current_user.id,
        status=status,
        priority=priority,
        start_date=start_date,
        end_date=end_date,
        lead_id=lead_id,
    )
    db.session.add(project)
    db.session.commit()
    
    # Add creator as a member by default
    project.members.append(current_user)

    # Add additional selected members
    for mid in member_ids:
        u = User.query.get(int(mid))
        if u and u not in project.members:
            project.members.append(u)
            if u.id != current_user.id:
                create_notification(
                    user_id=u.id,
                    title="Added to Project",
                    message=f"You have been added to project: {project.title}",
                    type="info",
                    link=url_for('projects.project_details', project_id=project.id)
                )

    db.session.commit()
    flash('Project created successfully', 'success')
    return redirect(url_for('projects.list_projects'))


@bp.route('/<int:project_id>')
@login_required
def project_details(project_id):
    active_org_id = session.get('active_org_id')
    project = Project.query.get_or_404(project_id)
    
    # Verify organization access
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    sprints = project.sprints.all()
    active_sprint = next((s for s in sprints if s.is_active), None)
    # Only show top-level tasks in backlog (subtasks inherit sprint from parent)
    backlog_tasks = project.tasks.filter_by(sprint_id=None, parent_id=None).all()
    documents = project.documents.order_by(Document.updated_at.desc()).all()
    
    task_page = request.args.get('task_page', 1, type=int)
    tasks_pagination = project.tasks.filter_by(parent_id=None).order_by(Task.created_at.desc()).paginate(page=task_page, per_page=20, error_out=False)
    
    # Get all organization users for assignee dropdown
    org_members = [m.user for m in Membership.query.filter_by(organization_id=active_org_id).all()]
    
    membership = Membership.query.filter_by(user_id=current_user.id, organization_id=active_org_id).first()
    is_admin = membership and membership.role == 'ADMIN'
    
    return render_template('projects/project_details.html', 
                           project=project, 
                           sprints=sprints, 
                           backlog_tasks=backlog_tasks, 
                           active_sprint=active_sprint, 
                           tasks_pagination=tasks_pagination,
                           documents=documents,
                           org_members=org_members,
                           datetime=datetime,
                           is_admin=is_admin)

@bp.route('/<int:project_id>/sprint/create', methods=['POST'])
@login_required
def create_sprint(project_id):
    project = Project.query.get_or_404(project_id)
    title = request.form.get('title', 'New Sprint')
    end_date_str = request.form.get('end_date')
    
    end_date = None
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            pass
            
    sprint = Sprint(title=title, project_id=project.id, end_date=end_date)
    db.session.add(sprint)
    db.session.commit()
    flash(f'Sprint "{title}" created.', 'success')
    return redirect(url_for('projects.project_details', project_id=project_id, tab='backlog'))

@bp.route('/sprint/<int:sprint_id>/start', methods=['POST'])
@login_required
def start_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    # Deactivate other sprints in this project
    Sprint.query.filter_by(project_id=sprint.project_id).update({Sprint.is_active: False})
    sprint.is_active = True
    sprint.start_date = datetime.utcnow()
    db.session.commit()
    task_count = sprint.tasks.count()
    flash(f'Sprint "{sprint.title}" started with {task_count} issue(s)!', 'success')
    return redirect(url_for('projects.project_details', project_id=sprint.project_id, tab='board'))

@bp.route('/sprint/<int:sprint_id>/complete', methods=['POST'])
@login_required
def complete_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    sprint.is_active = False
    sprint.end_date = datetime.utcnow()
    
    # Mark all incomplete tasks in this sprint as Done
    incomplete_tasks = sprint.tasks.filter(Task.status != 'Done').all()
    completed_count = 0
    for task in incomplete_tasks:
        task.status = 'Done'
        completed_count += 1
    
    # Also complete ALL subtasks whose parent is in this sprint, regardless of subtask's own sprint_id
    parent_ids = [t.id for t in sprint.tasks.all()]
    if parent_ids:
        orphan_subtasks = Task.query.filter(
            Task.parent_id.in_(parent_ids),
            Task.status != 'Done'
        ).all()
        for subtask in orphan_subtasks:
            subtask.status = 'Done'
            completed_count += 1
    
    db.session.commit()
    if completed_count > 0:
        flash(f'Sprint "{sprint.title}" completed. {completed_count} issue(s)/subtask(s) marked as Done.', 'success')
    else:
        flash(f'Sprint "{sprint.title}" completed. All tasks were already Done.', 'success')
    return redirect(url_for('projects.project_details', project_id=sprint.project_id, tab='backlog'))

@bp.route('/tasks/<int:task_id>/move-to-sprint', methods=['POST'])
@login_required
def move_to_sprint(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    sprint_id = data.get('sprint_id') # Can be None for Backlog
    
    new_sprint_id = int(sprint_id) if sprint_id and str(sprint_id).isdigit() else None
    task.sprint_id = new_sprint_id
    
    # Cascade: move all subtasks to the same sprint as the parent
    for subtask in task.subtasks:
        subtask.sprint_id = new_sprint_id
    
    db.session.commit()
    return {'success': True}

@bp.route('/<int:project_id>/sprint/<int:sprint_id>/activate', methods=['POST'])
@login_required
def activate_sprint(project_id, sprint_id):
    project = Project.query.get_or_404(project_id)
    sprint = Sprint.query.get_or_404(sprint_id)
    
    # Deactivate others
    for s in project.sprints.all():
        s.is_active = False
        
    sprint.is_active = True
    sprint.start_date = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('projects.project_details', project_id=project.id) + '?tab=board')
@bp.route('/<int:project_id>/add_member', methods=['POST'])
@login_required
def add_member(project_id):
    project = Project.query.get_or_404(project_id)
    user_id = request.form.get('user_id')
    if user_id:
        user = User.query.get(int(user_id))
        if user and user not in project.members:
            project.members.append(user)
            db.session.commit()
            flash(f'{user.username} added to project', 'success')
        else:
            flash('User already a member or not found', 'warning')
    return redirect(url_for('projects.project_details', project_id=project.id) + '?tab=settings')

@bp.route('/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    active_org_id = session.get('active_org_id')
    project = Project.query.get_or_404(project_id)
    
    # Verify organization access
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
        
    # Verify user is ADMIN in the current organization
    membership = Membership.query.filter_by(
        user_id=current_user.id, organization_id=active_org_id
    ).first()
    is_admin = membership and membership.role == 'ADMIN'
    
    if not is_admin:
        flash('Access denied. Only workspace administrators can delete projects.', 'error')
        return redirect(url_for('projects.project_details', project_id=project.id))
        
    project_title = project.title
    db.session.delete(project)
    db.session.commit()
    
    flash(f'Project "{project_title}" has been permanently deleted.', 'success')
    return redirect(url_for('projects.list_projects'))

@bp.route('/sprint/<int:sprint_id>/edit', methods=['POST'])
@login_required
def edit_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    project_id = sprint.project_id
    project = Project.query.get_or_404(project_id)
    
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
        
    new_title = request.form.get('title', '').strip()
    if not new_title:
        flash('Sprint title cannot be empty.', 'error')
        return redirect(url_for('projects.project_details', project_id=project_id, tab='backlog'))
        
    sprint.title = new_title
    db.session.commit()
    
    flash('Sprint title updated.', 'success')
    return redirect(url_for('projects.project_details', project_id=project_id, tab='backlog'))

@bp.route('/sprint/<int:sprint_id>/delete', methods=['POST'])
@login_required
def delete_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    project_id = sprint.project_id
    project = Project.query.get_or_404(project_id)
    
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
        
    title = sprint.title
    
    # Delete all tasks and subtasks associated with this sprint
    deleted_task_count = 0
    for task in sprint.tasks.all():
        for subtask in task.subtasks:
            db.session.delete(subtask)
            deleted_task_count += 1
        db.session.delete(task)
        deleted_task_count += 1
        
    db.session.delete(sprint)
    db.session.commit()
    
    flash(f'Sprint "{title}" and its {deleted_task_count} associated task(s)/subtask(s) have been deleted.', 'success')
    return redirect(url_for('projects.project_details', project_id=project_id, tab='backlog'))

@bp.route('/<int:project_id>/edit', methods=['POST'])
@login_required
@requires_project_manager
def edit_project(project_id):
    active_org_id = session.get('active_org_id')
    project = Project.query.get_or_404(project_id)
    
    # Verify organization access
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
        
    title = request.form.get('title', '').strip()[:100]
    description = request.form.get('description', '').strip()[:2000]
    status = request.form.get('status', '').strip()
    priority = request.form.get('priority', '').strip()
    start_date_raw = request.form.get('start_date', '').strip()
    end_date_raw = request.form.get('end_date', '').strip()
    
    if not (title and status and priority and start_date_raw and end_date_raw):
        flash('All fields except description are required to update the project.', 'error')
        return redirect(url_for('projects.project_details', project_id=project.id, tab='settings'))
        
    try:
        start_date = datetime.strptime(start_date_raw, '%Y-%m-%d')
    except ValueError:
        start_date = project.start_date
        
    try:
        end_date = datetime.strptime(end_date_raw, '%Y-%m-%d')
    except ValueError:
        end_date = project.end_date
        
    if end_date and start_date and end_date < start_date:
        flash('End date cannot be earlier than start date.', 'error')
        return redirect(url_for('projects.project_details', project_id=project.id, tab='settings'))
        
    project.title = title
    project.description = description
    project.status = status
    project.priority = priority
    project.start_date = start_date
    project.end_date = end_date
    
    db.session.commit()
    flash('Project details updated successfully.', 'success')
    return redirect(url_for('projects.project_details', project_id=project.id, tab='settings'))

@bp.route('/<int:project_id>/attach', methods=['POST'])
@login_required
def attach_file(project_id):
    from flask import current_app, session
    from werkzeug.utils import secure_filename
    from app.models import Attachment
    import os

    project = Project.query.get_or_404(project_id)
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    file = request.files.get('file')

    if file and file.filename:
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'csv', 'txt', 'zip', 'xls', 'xlsx'}
        MAX_FILE_SIZE_MB = 10
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            flash(f'File type not allowed: {ext}', 'error')
            return redirect(url_for('projects.project_details', project_id=project.id) + '?tab=docs')

        file_data = file.read()
        if len(file_data) > MAX_FILE_SIZE_MB * 1024 * 1024:
            flash(f'File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.', 'error')
            return redirect(url_for('projects.project_details', project_id=project.id) + '?tab=docs')
        file.seek(0)

        filename = secure_filename(file.filename)
        upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'attachments')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)

        file.save(os.path.join(upload_path, filename))

        attachment = Attachment(
            filename=file.filename,
            file_path=f"uploads/attachments/{filename}",
            project_id=project.id,
            uploaded_by_id=current_user.id
        )
        db.session.add(attachment)
        db.session.commit()
        flash('Document uploaded successfully', 'success')

    return redirect(url_for('projects.project_details', project_id=project.id) + '?tab=docs')

@bp.route('/attachment/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    from flask import current_app, session
    from app.models import Attachment
    import os

    attachment = Attachment.query.get_or_404(attachment_id)
    project_id = attachment.project_id
    project = Project.query.get_or_404(project_id)
    
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
        
    try:
        file_path = os.path.join(current_app.root_path, 'static', attachment.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error deleting file: {e}")
        
    db.session.delete(attachment)
    db.session.commit()
    flash('Attachment deleted successfully', 'success')
    
    return redirect(url_for('projects.project_details', project_id=project_id) + '?tab=docs')
