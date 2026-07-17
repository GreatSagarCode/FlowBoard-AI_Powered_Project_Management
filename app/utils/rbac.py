from functools import wraps
from flask import abort, flash, redirect, request, url_for
from flask_login import current_user
from app.models import Project, Membership

def requires_project_manager(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        project_id = kwargs.get('project_id')
        if not project_id:
            # Maybe the parameter is different, e.g. task_id
            task_id = kwargs.get('task_id')
            if task_id:
                from app.models import Task
                task = Task.query.get(task_id)
                if task:
                    project_id = task.project_id
            
            sprint_id = kwargs.get('sprint_id')
            if sprint_id:
                from app.models import Sprint
                sprint = Sprint.query.get(sprint_id)
                if sprint:
                    project_id = sprint.project_id
                    
        if not project_id and request.method in ['POST', 'PUT', 'PATCH']:
            if request.is_json:
                project_id = request.json.get('project_id')
            else:
                project_id = request.form.get('project_id')
                
        if not project_id:
            return f(*args, **kwargs)

        project = Project.query.get_or_404(project_id)
        
        # Determine if user is manager
        is_manager = False
        
        # Condition 1: User is project lead
        if project.lead_id == current_user.id:
            is_manager = True
            
        # Condition 2: User is project creator
        if project.created_by_id == current_user.id:
            is_manager = True
            
        # Condition 3: User is Workspace Admin
        org_membership = Membership.query.filter_by(
            user_id=current_user.id, 
            organization_id=project.organization_id
        ).first()
        if org_membership and org_membership.role == 'ADMIN':
            is_manager = True
            
        if not is_manager:
            flash('Access denied. You must be a Project Manager or Workspace Admin to perform this action.', 'error')
            return redirect(url_for('main.index'))
            
        return f(*args, **kwargs)
    return decorated_function
