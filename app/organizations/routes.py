import os
import re
from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.organizations import bp
from app.models import Organization, Membership, User, PendingInvitation
from app.extensions import db
import secrets
from app.utils.notifications import create_notification


def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    has_workspaces = current_user.memberships.count() > 0
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug') or slugify(name)

        # Check if slug exists
        if Organization.query.filter_by(slug=slug).first():
            flash('This workspace slug is already taken.', 'error')
            return redirect(url_for('organizations.create'))

        logo = request.files.get('logo')
        logo_path = None
        if logo and logo.filename:
            filename = secure_filename(f"{slug}_{logo.filename}")
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)
            logo.save(os.path.join(upload_path, filename))
            logo_path = f"uploads/logos/{filename}"

        org = Organization(name=name, slug=slug, logo_path=logo_path)
        db.session.add(org)
        db.session.commit()

        # Add creator as ADMIN
        membership = Membership(user_id=current_user.id, organization_id=org.id, role='ADMIN')
        db.session.add(membership)
        db.session.commit()

        session['active_org_id'] = org.id
        # Redirect to invite step instead of dashboard
        return redirect(url_for('organizations.invite_step'))

    # If user already has an org, render the embedded dashboard-integrated form
    if has_workspaces:
        return render_template('organizations/create_embedded.html')
    return render_template('organizations/create.html', has_workspaces=has_workspaces)


@bp.route('/invite-step', methods=['GET'])
@login_required
def invite_step():
    """Show the invite new members modal/page after org creation."""
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)
    if not org:
        return redirect(url_for('main.index'))
    return render_template('organizations/invite.html', org=org)


@bp.route('/invite', methods=['POST'])
@login_required
def invite():
    """Process invitations — find users by email and add them to the org."""
    active_org_id = session.get('active_org_id')
    org = Organization.query.get(active_org_id)
    if not org:
        flash('No active workspace found.', 'error')
        return redirect(url_for('main.index'))

    emails_raw = request.form.get('emails', '')
    role = request.form.get('role', 'MEMBER').upper()
    if role not in ('MEMBER', 'CONTRIBUTOR'):
        role = 'MEMBER'

    emails = [e.strip() for e in emails_raw.replace('\n', ',').split(',') if e.strip()]
    project_id = request.form.get('project_id')
    project = None
    if project_id:
        from app.models import Project
        project = Project.query.get(project_id)

    invited = 0
    not_found = []

    for email in emails:
        user = User.query.filter_by(email=email).first()
        if user:
            # Check already a member of org
            existing = Membership.query.filter_by(
                user_id=user.id, organization_id=org.id
            ).first()
            if not existing:
                m = Membership(user_id=user.id, organization_id=org.id, role=role)
                db.session.add(m)
                
                # Notify the user they were added to the workspace
                create_notification(
                    user_id=user.id,
                    title="Added to Workspace",
                    message=f"You have been added to the workspace: {org.name}",
                    type="success",
                    link=url_for('main.index')
                )
            
            # If a project is specified, add them to it
            if project and user not in project.members:
                project.members.append(user)
                create_notification(
                    user_id=user.id,
                    title="Added to Project",
                    message=f"You have been added to project: {project.title}",
                    type="info",
                    link=url_for('projects.project_details', project_id=project.id)
                )
            
            invited += 1
        else:
            # Generate PendingInvitation
            token = secrets.token_urlsafe(32)
            pending = PendingInvitation(
                email=email,
                organization_id=org.id,
                role=role,
                token=token
            )
            db.session.add(pending)
            # Simulated email (flash it)
            invite_url = url_for('auth.register', token=token, email=email, _external=True)
            print(f"SIMULATED EMAIL TO {email}: Join {org.name} -> {invite_url}")
            flash(f"Invitation sent to {email} (Check console for URL).", "success")
            not_found.append(email)

    db.session.commit()

    if invited:
        flash(f'{invited} member(s) successfully added.', 'success')

    if project_id:
        return redirect(url_for('projects.project_details', project_id=project_id) + '?tab=settings')
    return redirect(url_for('main.index'))


@bp.route('/switch/<string:slug>')
@login_required
def switch(slug):
    org = Organization.query.filter_by(slug=slug).first_or_404()
    # Verify membership
    membership = Membership.query.filter_by(
        user_id=current_user.id, organization_id=org.id
    ).first()
    if not membership:
        flash('You are not a member of this workspace.', 'error')
        return redirect(url_for('main.index'))

    session['active_org_id'] = org.id
    flash(f'Switched to {org.name}', 'success')
    return redirect(url_for('main.index'))
