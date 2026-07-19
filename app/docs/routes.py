"""Document routes — create, edit, delete rich text documents."""
from flask import render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from app.docs import bp
from app.models import Document, Project
from app.extensions import db
from datetime import datetime
from app.utils import get_membership

@bp.route('/project/<int:project_id>/create', methods=['GET', 'POST'])
@login_required
def create(project_id):
    project = Project.query.get_or_404(project_id)
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    if not get_membership():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    membership = get_membership()
    if membership and membership.role == 'CONTRIBUTOR':
        flash('Contributors cannot create documents.', 'error')
        return redirect(url_for('projects.project_details', project_id=project_id) + '?tab=docs')

    if request.method == 'POST':
        title = request.form.get('title', '').strip()[:200]
        content = request.form.get('content', '').strip()
        import bleach
        allowed_tags = ['h1', 'h2', 'h3', 'p', 'br', 'strong', 'em', 'u', 's', 'blockquote', 'pre', 'ol', 'ul', 'li', 'a', 'img', 'span']
        allowed_attrs = {'*': ['class', 'style'], 'a': ['href', 'target'], 'img': ['src', 'alt']}
        if content:
            content = bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs, styles=['color', 'background-color'])
        
        if not title:
            flash('Title is required', 'error')
            return redirect(url_for('docs.create', project_id=project_id))
            
        task_id = request.form.get('task_id')
        if task_id and not task_id.strip():
            task_id = None
        elif task_id:
            try:
                task_id = int(task_id)
            except ValueError:
                task_id = None
            
        doc = Document(
            title=title,
            content=content,
            project_id=project_id,
            task_id=task_id,
            author_id=current_user.id
        )
        db.session.add(doc)
        db.session.commit()
        flash('Document created successfully', 'success')
        return redirect(url_for('projects.project_details', project_id=project_id) + '?tab=docs')
        
    return render_template('docs/edit.html', project=project)

@bp.route('/<int:doc_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(doc_id):
    doc = Document.query.get_or_404(doc_id)
    project = doc.project
    
    active_org_id = session.get('active_org_id')
    if project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    if not get_membership():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    membership = get_membership()
    if membership and membership.role == 'CONTRIBUTOR':
        flash('Contributors cannot edit documents.', 'error')
        return redirect(url_for('projects.project_details', project_id=project.id) + '?tab=docs')

    if request.method == 'POST':
        doc.title = (request.form.get('title') or '')[:200]
        content = request.form.get('content', '').strip()
        import bleach
        allowed_tags = ['h1', 'h2', 'h3', 'p', 'br', 'strong', 'em', 'u', 's', 'blockquote', 'pre', 'ol', 'ul', 'li', 'a', 'img', 'span']
        allowed_attrs = {'*': ['class', 'style'], 'a': ['href', 'target'], 'img': ['src', 'alt']}
        if content:
            doc.content = bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs, styles=['color', 'background-color'])
        else:
            doc.content = ''
        
        task_id = request.form.get('task_id')
        if task_id and not task_id.strip():
            task_id = None
        elif task_id:
            try:
                task_id = int(task_id)
            except ValueError:
                task_id = None
        doc.task_id = task_id
            
        doc.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Document updated successfully', 'success')
        return redirect(url_for('projects.project_details', project_id=project.id) + '?tab=docs')
        
    return render_template('docs/edit.html', doc=doc, project=project)

@bp.route('/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete(doc_id):
    doc = Document.query.get_or_404(doc_id)
    project_id = doc.project_id
    
    active_org_id = session.get('active_org_id')
    if doc.project.organization_id != active_org_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    if not get_membership():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    project = doc.project
    membership = get_membership()
    can_delete = False
    if membership and membership.role == 'ADMIN':
        can_delete = True
    elif project.lead_id == current_user.id or project.created_by_id == current_user.id:
        can_delete = True

    if not can_delete:
        flash('You do not have permission to delete this document.', 'error')
        return redirect(url_for('projects.project_details', project_id=project_id) + '?tab=docs')

    db.session.delete(doc)
    db.session.commit()
    flash('Document deleted', 'success')
    return redirect(url_for('projects.project_details', project_id=project_id) + '?tab=docs')
