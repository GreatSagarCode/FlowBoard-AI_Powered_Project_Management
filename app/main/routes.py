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

    projects = Project.query.filter_by(organization_id=active_org_id).all()
    project_ids = [p.id for p in projects]

    all_tasks = Task.query.filter(Task.project_id.in_(project_ids)).all() if project_ids else []

    total_projects = len(projects)
    completed_projects = len([p for p in projects if p.status in ('COMPLETED', 'DONE') or p.progress == 100])
    my_tasks_count = len([t for t in all_tasks if t.assignee_id == current_user.id and t.status != 'Done'])
    overdue_tasks_count = len([
        t for t in all_tasks
        if t.due_date and t.due_date < datetime.utcnow() and t.status != 'Done'
    ])

    recent_tasks = sorted(all_tasks, key=lambda x: x.created_at, reverse=True)[:5]
    my_tasks = [t for t in all_tasks if t.assignee_id == current_user.id][:5]
    overdue_tasks = [
        t for t in all_tasks
        if t.due_date and t.due_date < datetime.utcnow() and t.status != 'Done'
    ][:5]
    in_progress_tasks = [t for t in all_tasks if t.status == 'In Progress'][:5]

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

    memberships = Membership.query.filter_by(organization_id=active_org_id).all()
    members = [m.user for m in memberships]
    member_roles = {m.user_id: m.role for m in memberships}

    projects = Project.query.filter_by(organization_id=active_org_id).all()
    project_ids = [p.id for p in projects]
    all_tasks = Task.query.filter(Task.project_id.in_(project_ids)).all() if project_ids else []

    active_projects_count = len([p for p in projects if p.status not in ('COMPLETED', 'DONE')])

    return render_template('main/team.html',
                           org=org,
                           members=members,
                           member_roles=member_roles,
                           total_members=len(members),
                           active_projects_count=active_projects_count,
                           total_tasks=len(all_tasks))


@bp.route('/team/invite', methods=['POST'])
@login_required
def team_invite():
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)
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
    return redirect(request.referrer or url_for('main.index'))


@bp.route('/notifications/read-all')
@login_required
def mark_all_read():
    current_user.notifications.filter_by(is_read=False).update({Notification.is_read: True})
    db.session.commit()
    return redirect(request.referrer or url_for('main.index'))

@bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)
    
    if not query or not active_org_id:
        return render_template('main/search_results.html', org=org, query=query, projects=[], tasks=[])
        
    projects = Project.query.filter(
        Project.organization_id == active_org_id,
        Project.title.ilike(f'%{query}%') | Project.description.ilike(f'%{query}%')
    ).all()
    
    project_ids = [p.id for p in Project.query.filter_by(organization_id=active_org_id).all()]
    tasks = Task.query.filter(
        Task.project_id.in_(project_ids),
        Task.title.ilike(f'%{query}%') | Task.description.ilike(f'%{query}%')
    ).all() if project_ids else []
    
    return render_template('main/search_results.html', org=org, query=query, projects=projects, tasks=tasks)
