from flask import render_template, redirect, url_for, session, request, flash, jsonify
from flask_login import login_required, current_user
from app.main import bp
from app.models import Project, Task, Organization, Membership, User, Notification
from app.extensions import db
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from flask import current_app


@bp.before_app_request
def ensure_org():
    if current_user.is_authenticated:
        # Exempt routes
        if request.endpoint and (
            'organizations.' in request.endpoint or
            'auth.' in request.endpoint or
            'static' in request.endpoint
        ):
            return None

        # Try to find an active org in session
        active_org_id = session.get('active_org_id')
        if active_org_id:
            membership = Membership.query.filter_by(
                user_id=current_user.id, organization_id=active_org_id
            ).first()
            if membership:
                return None

        # If no active org in session, check if user has any memberships
        first_membership = current_user.memberships.first()
        if first_membership:
            session['active_org_id'] = first_membership.organization_id
            return None

        # No memberships — redirect to create org
        return redirect(url_for('organizations.create'))

    return None


@bp.route('/')
@login_required
def index():
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)

    # 1. Base Project Query (optimized, no loading all tasks)
    projects_query = Project.query.filter_by(organization_id=active_org_id)
    projects = projects_query.limit(10).all() # Only load up to 10 for dashboard preview
    project_ids = [p.id for p in projects_query.with_entities(Project.id).all()]
    total_projects = projects_query.count()
    completed_projects = projects_query.filter(Project.status.in_(['COMPLETED', 'DONE'])).count()

    if not project_ids:
        my_tasks_count = overdue_tasks_count = 0
        recent_tasks = my_tasks = overdue_tasks = in_progress_tasks = []
    else:
        # Base Task query bounded by organization projects
        base_task_query = Task.query.filter(Task.project_id.in_(project_ids))
        
        # Fast SQL counts instead of len([t for t in all_tasks])
        my_tasks_count = base_task_query.filter(Task.assignee_id == current_user.id, Task.status != 'Done').count()
        overdue_tasks_count = base_task_query.filter(Task.due_date != None, Task.due_date < datetime.utcnow(), Task.status != 'Done').count()

        # Paginated/Limited queries for dashboard views
        recent_tasks = base_task_query.order_by(Task.created_at.desc()).limit(5).all()
        my_tasks = base_task_query.filter(Task.assignee_id == current_user.id).order_by(Task.due_date.asc()).limit(5).all()
        overdue_tasks = base_task_query.filter(Task.due_date != None, Task.due_date < datetime.utcnow(), Task.status != 'Done').limit(5).all()
        in_progress_tasks = base_task_query.filter(Task.status == 'In Progress').limit(5).all()

    # Get org members
    memberships = Membership.query.filter_by(organization_id=active_org_id).all()
    org_members = [m.user for m in memberships]

    return render_template('main/dashboard.html',
                           org=org,
                           projects=projects,
                           total_projects=total_projects,
                           completed_projects=completed_projects,
                           my_tasks_count=my_tasks_count,
                           overdue_tasks_count=overdue_tasks_count,
                           recent_tasks=recent_tasks,
                           my_tasks=my_tasks,
                           overdue_tasks=overdue_tasks,
                           in_progress_tasks=in_progress_tasks,
                           org_members=org_members)


@bp.route('/team')
@login_required
def team():
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)

    # Use pagination for memberships (fallback to all if needed, but safer)
    page = request.args.get('page', 1, type=int)
    memberships = Membership.query.filter_by(organization_id=active_org_id).paginate(page=page, per_page=50, error_out=False)
    members = [m.user for m in memberships.items]
    member_roles = {m.user_id: m.role for m in memberships.items}
    total_members = memberships.total

    projects_query = Project.query.filter_by(organization_id=active_org_id)
    project_ids = [p.id for p in projects_query.with_entities(Project.id).all()]
    
    active_projects_count = projects_query.filter(~Project.status.in_(['COMPLETED', 'DONE'])).count()
    total_tasks = Task.query.filter(Task.project_id.in_(project_ids)).count() if project_ids else 0

    return render_template('main/team.html',
                           org=org,
                           members=members,
                           member_roles=member_roles,
                           total_members=total_members,
                           active_projects_count=active_projects_count,
                           total_tasks=total_tasks,
                           pagination=memberships)


@bp.route('/team/invite', methods=['POST'])
@login_required
def team_invite():
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)
    
    membership = Membership.query.filter_by(user_id=current_user.id, organization_id=active_org_id).first()
    if not membership or membership.role == 'CONTRIBUTOR':
        flash('Contributors are not allowed to invite others.', 'error')
        return redirect(url_for('main.team'))
        
    email = request.form.get('email', '').strip()
    role = request.form.get('role', 'MEMBER').upper()
    if role not in ('MEMBER', 'CONTRIBUTOR'):
        role = 'MEMBER'

    user = User.query.filter_by(email=email).first()
    if not user:
        flash(f'No account found for "{email}". They must register first.', 'error')
    else:
        existing = Membership.query.filter_by(user_id=user.id, organization_id=org.id).first()
        if existing:
            flash(f'{user.username} is already a member.', 'error')
        else:
            m = Membership(user_id=user.id, organization_id=org.id, role=role)
            db.session.add(m)
            db.session.commit()
            flash(f'{user.username} added to {org.name}.', 'success')

    return redirect(url_for('main.team'))


@bp.route('/team/remove/<int:user_id>', methods=['POST'])
@login_required
def team_remove(user_id):
    active_org_id = session.get('active_org_id')
    # Verify current_user is ADMIN
    membership = Membership.query.filter_by(
        user_id=current_user.id, organization_id=active_org_id
    ).first()
    
    if not membership or membership.role != 'ADMIN':
        flash('Only admins can remove members.', 'error')
        return redirect(url_for('main.team'))
    
    target = Membership.query.filter_by(user_id=user_id, organization_id=active_org_id).first()
    if not target:
        flash('User is not in the workspace.', 'error')
        return redirect(url_for('main.team'))
        
    if target.role == 'ADMIN':
        flash('Cannot remove the workspace admin.', 'error')
        return redirect(url_for('main.team'))
        
    db.session.delete(target)
    db.session.commit()
    flash('Member removed successfully.', 'success')
    return redirect(url_for('main.team'))

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)

    # Verify user is ADMIN
    membership = Membership.query.filter_by(
        user_id=current_user.id, organization_id=active_org_id
    ).first()
    is_admin = membership and membership.role == 'ADMIN'

    if request.method == 'POST':
        if not is_admin:
            flash('Only admins can update workspace settings.', 'error')
            return redirect(url_for('main.settings'))

        name = request.form.get('name', '').strip()
        if name:
            org.name = name

        logo = request.files.get('logo')
        if logo and logo.filename:
            ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
            MAX_LOGO_SIZE_MB = 2
            ext = logo.filename.rsplit('.', 1)[1].lower() if '.' in logo.filename else ''
            if ext not in ALLOWED_LOGO_EXTENSIONS:
                flash(f'Logo file type not allowed: {ext}. Use PNG, JPG, GIF, WEBP, or SVG.', 'error')
                return redirect(url_for('main.settings'))
            logo_data = logo.read()
            if len(logo_data) > MAX_LOGO_SIZE_MB * 1024 * 1024:
                flash(f'Logo file too large. Maximum size is {MAX_LOGO_SIZE_MB}MB.', 'error')
                return redirect(url_for('main.settings'))
            logo.seek(0)
            import re
            slug = re.sub(r'[^a-z0-9]+', '-', org.slug)
            filename = secure_filename(f"{slug}_{logo.filename}")
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)
            logo.save(os.path.join(upload_path, filename))
            org.logo_path = f"uploads/logos/{filename}"

        db.session.commit()
        flash('Workspace settings updated.', 'success')
        return redirect(url_for('main.settings'))

    memberships = Membership.query.filter_by(organization_id=active_org_id).all()
    return render_template('main/settings.html', org=org, is_admin=is_admin,
                           memberships=memberships)


@bp.route('/settings/delete-workspace', methods=['POST'])
@login_required
def delete_workspace():
    active_org_id = session.get('active_org_id')
    if not active_org_id:
        flash('No active workspace found.', 'error')
        return redirect(url_for('main.index'))

    # Verify user is ADMIN
    membership = Membership.query.filter_by(
        user_id=current_user.id, organization_id=active_org_id
    ).first()
    if not membership or membership.role != 'ADMIN':
        flash('Only workspace administrators can delete the workspace.', 'error')
        return redirect(url_for('main.settings'))

    org = Organization.query.get(active_org_id)
    if org:
        db.session.delete(org)
        db.session.commit()
        session.pop('active_org_id', None)
        flash('Workspace deleted successfully.', 'success')

    return redirect(url_for('main.index'))


@bp.route('/ml/suggest', methods=['POST'])
@login_required
def ml_suggest():
    from app.services.ml_service import MLService
    
    data = request.get_json()
    title = data.get('title', '')
    description = data.get('description', '')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
        
    suggestion = MLService.suggest_for_project(title, description)
    
    return jsonify(suggestion)


@bp.route('/notifications')
@login_required
def notifications():
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)
    # Get unread count for badge
    unread_notifications = current_user.notifications.filter_by(is_read=False).order_by(Notification.created_at.desc()).all()
    all_notifications = current_user.notifications.order_by(Notification.created_at.desc()).all()
    return render_template('main/notifications.html', 
                           org=org, 
                           unread_notifications=unread_notifications,
                           all_notifications=all_notifications)


@bp.route('/notifications/read/<int:id>')
@login_required
def mark_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return redirect(url_for('main.index'))


@bp.route('/notifications/read-all')
@login_required
def mark_all_read():
    current_user.notifications.filter_by(is_read=False).update({Notification.is_read: True})
    db.session.commit()
    return redirect(url_for('main.index'))

@bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)

    # Filter params
    status_filter = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    assignee_filter = request.args.get('assignee', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    # Get org members for the assignee filter dropdown
    org_members = [m.user for m in Membership.query.filter_by(organization_id=active_org_id).all()] if active_org_id else []

    if not active_org_id:
        return render_template('main/search_results.html', org=org, query=query,
                               projects=[], tasks=[], org_members=org_members,
                               status_filter=status_filter, priority_filter=priority_filter,
                               assignee_filter=assignee_filter, date_from=date_from, date_to=date_to)

    # Use parameterized queries via SQLAlchemy's built-in parameterization
    search_term = f'%{query}%' if query else None

    # --- Project search (parameterized) ---
    project_query = Project.query.filter(Project.organization_id == active_org_id)
    if search_term:
        project_query = project_query.filter(
            db.or_(
                Project.title.ilike(search_term),
                Project.description.ilike(search_term)
            )
        )
    if status_filter:
        project_query = project_query.filter(Project.status == status_filter)
    if priority_filter:
        project_query = project_query.filter(Project.priority == priority_filter)
    projects = project_query.order_by(Project.updated_at.desc()).limit(50).all()

    # --- Task search (parameterized with filters) ---
    project_ids = [p.id for p in Project.query.filter_by(organization_id=active_org_id).with_entities(Project.id).all()]
    tasks = []
    if project_ids:
        task_query = Task.query.filter(Task.project_id.in_(project_ids))
        if search_term:
            task_query = task_query.filter(
                db.or_(
                    Task.title.ilike(search_term),
                    Task.description.ilike(search_term)
                )
            )
        if status_filter:
            task_query = task_query.filter(Task.status == status_filter)
        if priority_filter:
            task_query = task_query.filter(Task.priority == priority_filter)
        if assignee_filter and assignee_filter.isdigit():
            task_query = task_query.filter(Task.assignee_id == int(assignee_filter))
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                task_query = task_query.filter(Task.due_date >= date_from_dt)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                task_query = task_query.filter(Task.due_date <= date_to_dt)
            except ValueError:
                pass
        tasks = task_query.order_by(Task.updated_at.desc()).limit(100).all()

    return render_template('main/search_results.html', org=org, query=query,
                           projects=projects, tasks=tasks, org_members=org_members,
                           status_filter=status_filter, priority_filter=priority_filter,
                           assignee_filter=assignee_filter, date_from=date_from, date_to=date_to)


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id) if active_org_id else None

    if request.method == 'POST':
        form_type = request.form.get('form_type', '')

        if form_type == 'avatar':
            avatar = request.files.get('avatar')
            if avatar and avatar.filename:
                ALLOWED_AVATAR_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                MAX_AVATAR_SIZE_MB = 2
                ext = avatar.filename.rsplit('.', 1)[1].lower() if '.' in avatar.filename else ''
                if ext not in ALLOWED_AVATAR_EXT:
                    flash(f'File type not allowed: {ext}. Use PNG, JPG, GIF, or WEBP.', 'error')
                    return redirect(url_for('main.profile'))
                avatar_data = avatar.read()
                if len(avatar_data) > MAX_AVATAR_SIZE_MB * 1024 * 1024:
                    flash(f'Avatar too large. Maximum size is {MAX_AVATAR_SIZE_MB}MB.', 'error')
                    return redirect(url_for('main.profile'))
                avatar.seek(0)

                filename = secure_filename(f"avatar_{current_user.id}_{avatar.filename}")
                upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)

                # Remove old avatar file if exists
                if current_user.avatar_path:
                    old_path = os.path.join(current_app.root_path, 'static', current_user.avatar_path)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass

                avatar.save(os.path.join(upload_path, filename))
                current_user.avatar_path = f"uploads/avatars/{filename}"
                db.session.commit()
                flash('Avatar updated successfully.', 'success')

        elif form_type == 'profile':
            from werkzeug.security import check_password_hash
            new_username = request.form.get('username', '').strip()[:64]
            new_email = request.form.get('email', '').strip()[:120]

            if not new_username or not new_email:
                flash('Username and email are required.', 'error')
                return redirect(url_for('main.profile'))

            # Validate email format
            from email_validator import validate_email, EmailNotValidError
            try:
                valid = validate_email(new_email)
                new_email = valid.email
            except EmailNotValidError as e:
                flash(str(e), 'error')
                return redirect(url_for('main.profile'))

            # Check uniqueness (excluding self)
            if new_username != current_user.username:
                existing = User.query.filter(User.username == new_username, User.id != current_user.id).first()
                if existing:
                    flash('Username already taken.', 'error')
                    return redirect(url_for('main.profile'))

            if new_email != current_user.email:
                existing = User.query.filter(User.email == new_email, User.id != current_user.id).first()
                if existing:
                    flash('Email already in use.', 'error')
                    return redirect(url_for('main.profile'))

            current_user.username = new_username
            current_user.email = new_email
            db.session.commit()
            flash('Profile updated successfully.', 'success')

        elif form_type == 'password':
            from werkzeug.security import check_password_hash, generate_password_hash
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not check_password_hash(current_user.password_hash, current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('main.profile'))

            if len(new_password) < 6:
                flash('New password must be at least 6 characters.', 'error')
                return redirect(url_for('main.profile'))

            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('main.profile'))

            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password changed successfully.', 'success')

        return redirect(url_for('main.profile'))

    return render_template('main/profile.html', org=org)
