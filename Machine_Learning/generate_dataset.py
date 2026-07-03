"""
Synthetic JIRA/GitHub Issues Dataset Generator
===============================================
Generates a realistic dataset of software project management issues
that maps to the application's exact categories and priorities.

Categories: Task, Feature, Bug, Design, Frontend, Backend, Devops, Docs
Priorities: Low, Medium, High, Highest
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

# ──────────────────────────────────────────────
# REALISTIC TITLE & DESCRIPTION TEMPLATES
# ──────────────────────────────────────────────

TEMPLATES = {
    "Bug": {
        "titles": [
            "Fix null pointer exception in {module}",
            "Resolve crash when {action} on {platform}",
            "Fix broken {feature} after latest update",
            "Handle edge case in {module} validation",
            "Fix memory leak in {module} service",
            "Resolve timeout error in {feature}",
            "Fix incorrect data display in {feature}",
            "Patch security vulnerability in {module}",
            "Fix race condition in {module} handler",
            "Resolve 500 error on {action}",
            "Fix layout break in {feature} component",
            "Debug flaky test in {module}",
            "Fix pagination bug in {feature}",
            "Resolve login failure on {platform}",
            "Fix data loss when {action}",
            "Correct wrong calculation in {feature}",
            "Fix broken redirect after {action}",
            "Resolve CORS error in {module} API",
            "Fix duplicate entries in {feature}",
            "Handle missing field validation in {module}",
        ],
        "descriptions": [
            "Users are experiencing {issue} when trying to {action}. This affects {impact}. Steps to reproduce: 1) Navigate to {feature} 2) Perform {action} 3) Observe the error.",
            "A critical bug has been identified in the {module} module causing {issue}. This needs immediate attention as it impacts {impact}.",
            "After the recent deployment, {feature} is throwing {issue}. The root cause appears to be in the {module} service layer.",
            "Intermittent {issue} reported by multiple users when {action}. Stack trace points to {module} handler.",
            "The {feature} feature fails silently when {action}. No error logs are generated, making debugging difficult.",
        ],
    },
    "Feature": {
        "titles": [
            "Implement {feature} for {module}",
            "Add {action} capability to {module}",
            "Create new {feature} dashboard widget",
            "Build {feature} notification system",
            "Implement real-time {feature} updates",
            "Add bulk {action} functionality",
            "Create {feature} analytics module",
            "Implement {feature} export to CSV",
            "Add {feature} search and filter",
            "Build {module} integration with {platform}",
            "Implement role-based access for {feature}",
            "Add drag-and-drop to {feature}",
            "Create automated {feature} workflow",
            "Implement {feature} scheduling system",
            "Add multi-language support for {module}",
            "Build {feature} reporting engine",
            "Implement SSO for {module}",
            "Add audit trail for {feature}",
            "Create {feature} template system",
            "Implement webhook support for {module}",
        ],
        "descriptions": [
            "As a user, I want to {action} so that I can improve my workflow. Acceptance criteria: 1) {feature} is accessible from {module} 2) Data is persisted correctly 3) UI updates in real-time.",
            "We need to implement {feature} in the {module} module. This will allow users to {action} and significantly improve productivity.",
            "Product requirement: Build a comprehensive {feature} system integrated with {module}. Must support {action} with proper validation and error handling.",
            "New feature request from stakeholders: {feature} capability in {module}. Should support bulk operations and {action}.",
        ],
    },
    "Task": {
        "titles": [
            "Update {module} configuration settings",
            "Refactor {module} service layer",
            "Migrate {feature} data to new schema",
            "Clean up deprecated {module} code",
            "Optimize {feature} database queries",
            "Update dependencies for {module}",
            "Configure CI/CD for {module} pipeline",
            "Set up monitoring for {feature}",
            "Review and merge {module} PR",
            "Update environment variables for {platform}",
            "Create test fixtures for {module}",
            "Reorganize {module} file structure",
            "Update {feature} error messages",
            "Archive old {feature} records",
            "Set up staging environment for {module}",
            "Run performance benchmark on {feature}",
            "Update SSL certificates for {platform}",
            "Configure rate limiting for {module} API",
            "Set up log rotation for {module}",
            "Update {feature} seed data",
        ],
        "descriptions": [
            "Routine maintenance task: {action} in the {module} module. Ensure all tests pass after changes.",
            "Technical debt item: {module} needs {action}. This will improve maintainability and reduce future bugs.",
            "Sprint task: Complete {action} for {feature}. Coordinate with the team for any blocking dependencies.",
            "Housekeeping task to {action} in {module}. Low risk, but important for long-term code health.",
        ],
    },
    "Design": {
        "titles": [
            "Design new {feature} UI mockup",
            "Create wireframe for {module} dashboard",
            "Redesign {feature} user flow",
            "Design {module} mobile layout",
            "Create icon set for {feature}",
            "Design {feature} onboarding screens",
            "Update color scheme for {module}",
            "Design {feature} empty state illustrations",
            "Create {module} style guide",
            "Design responsive layout for {feature}",
            "Prototype {feature} interaction patterns",
            "Design {module} dark mode theme",
            "Create loading animation for {feature}",
            "Design {feature} notification badges",
            "Update typography system for {module}",
            "Design {feature} settings page",
            "Create {module} logo variations",
            "Design {feature} data visualization charts",
            "Redesign {module} navigation menu",
            "Design {feature} accessibility improvements",
        ],
        "descriptions": [
            "Design a modern, intuitive UI for {feature} in {module}. Must follow our design system guidelines and be responsive across all breakpoints.",
            "Create high-fidelity mockups for the {feature} module. Include hover states, loading states, and error states.",
            "Redesign the {feature} experience to improve usability. Conduct user research and create wireframes before final design.",
            "Visual design task: Update {feature} in {module} to match the new brand guidelines. Deliver in Figma with proper component structure.",
        ],
    },
    "Frontend": {
        "titles": [
            "Build {feature} React component",
            "Implement {feature} form validation",
            "Create {feature} data table with sorting",
            "Add {feature} toast notifications",
            "Implement {module} state management",
            "Build {feature} modal dialog",
            "Create {feature} sidebar navigation",
            "Implement lazy loading for {feature}",
            "Build {feature} file upload widget",
            "Add keyboard shortcuts to {feature}",
            "Implement {feature} infinite scroll",
            "Build {feature} chart component",
            "Create {feature} breadcrumb navigation",
            "Implement {feature} autocomplete search",
            "Build {module} dropdown menu component",
            "Add {feature} skeleton loading screens",
            "Implement {feature} tab navigation",
            "Build {feature} calendar picker",
            "Create {feature} progress indicator",
            "Implement {feature} responsive grid layout",
        ],
        "descriptions": [
            "Frontend implementation: Build the {feature} component for {module}. Must be reusable, accessible (WCAG 2.1), and work across all supported browsers.",
            "Implement the client-side logic for {feature}. Use existing design tokens and component library. Include unit tests.",
            "Create a performant {feature} UI component. Optimize for re-renders and ensure smooth animations at 60fps.",
            "Build {feature} with proper error boundaries and loading states. Follow atomic design principles.",
        ],
    },
    "Backend": {
        "titles": [
            "Create REST API for {feature}",
            "Implement {module} authentication middleware",
            "Build {feature} data processing pipeline",
            "Create database migration for {module}",
            "Implement {feature} caching layer",
            "Build {module} background job processor",
            "Create {feature} webhook handler",
            "Implement {module} rate limiting",
            "Build {feature} file storage service",
            "Create {module} email notification service",
            "Implement {feature} search indexing",
            "Build {module} data validation layer",
            "Create {feature} audit logging system",
            "Implement {module} session management",
            "Build {feature} batch processing endpoint",
            "Create {module} GraphQL schema",
            "Implement {feature} data encryption",
            "Build {module} health check endpoint",
            "Create {feature} permission system",
            "Implement {module} database connection pooling",
        ],
        "descriptions": [
            "Backend development: Implement the {feature} service in {module}. Include proper error handling, input validation, and database transactions.",
            "Build a scalable {feature} API endpoint. Must handle concurrent requests and include proper logging.",
            "Create the server-side logic for {feature} in {module}. Follow RESTful conventions and include Swagger documentation.",
            "Implement {feature} backend with proper separation of concerns. Include service layer, repository pattern, and unit tests.",
        ],
    },
    "Devops": {
        "titles": [
            "Set up Docker container for {module}",
            "Configure Kubernetes deployment for {feature}",
            "Create CI/CD pipeline for {module}",
            "Set up monitoring dashboard for {feature}",
            "Configure auto-scaling for {module}",
            "Implement blue-green deployment for {feature}",
            "Set up log aggregation for {module}",
            "Configure SSL/TLS for {platform}",
            "Create backup strategy for {module} database",
            "Set up load balancer for {feature}",
            "Configure alerting rules for {module}",
            "Implement infrastructure as code for {platform}",
            "Set up secrets management for {module}",
            "Configure CDN for {feature} static assets",
            "Create disaster recovery plan for {module}",
            "Set up staging environment for {platform}",
            "Configure network policies for {module}",
            "Implement container registry for {feature}",
            "Set up performance profiling for {module}",
            "Configure database replication for {feature}",
        ],
        "descriptions": [
            "DevOps task: Set up infrastructure for {feature} in {module}. Must follow security best practices and be documented in the runbook.",
            "Infrastructure: Configure {feature} deployment pipeline. Include automated testing, staging validation, and rollback procedures.",
            "Create reliable deployment infrastructure for {module}. Include health checks, resource limits, and monitoring integration.",
            "Set up {feature} infrastructure with high availability and fault tolerance. Document all configuration in the wiki.",
        ],
    },
    "Docs": {
        "titles": [
            "Write API documentation for {module}",
            "Create user guide for {feature}",
            "Update README for {module} repository",
            "Document {feature} architecture decisions",
            "Write troubleshooting guide for {module}",
            "Create onboarding docs for {feature}",
            "Document {module} deployment process",
            "Write changelog for {feature} release",
            "Create {module} contribution guidelines",
            "Document {feature} database schema",
            "Write migration guide for {module}",
            "Create {feature} FAQ page",
            "Document {module} environment setup",
            "Write {feature} integration guide",
            "Create {module} security documentation",
            "Document {feature} testing strategy",
            "Write release notes for {module}",
            "Create {feature} best practices guide",
            "Document {module} error codes",
            "Write {feature} performance tuning guide",
        ],
        "descriptions": [
            "Documentation task: Write comprehensive docs for {feature} in {module}. Include code examples, diagrams, and troubleshooting tips.",
            "Create user-facing documentation for {feature}. Must be clear, concise, and include screenshots where applicable.",
            "Update technical documentation for {module}. Cover API endpoints, data models, and authentication flow.",
            "Write detailed documentation for {feature} including setup instructions, configuration options, and common pitfalls.",
        ],
    },
}

# Fill-in values
MODULES = ["user", "project", "task", "sprint", "notification", "auth", "report", "analytics", "payment", "billing", "inventory", "dashboard", "settings", "profile", "workflow"]
FEATURES = ["task board", "user management", "reporting", "search", "calendar", "timeline", "backlog", "sprint planning", "kanban", "file upload", "comments", "activity feed", "notifications", "permissions", "data export"]
ACTIONS = ["saving data", "uploading files", "filtering results", "submitting forms", "loading dashboard", "exporting reports", "deleting records", "updating profile", "syncing data", "generating reports"]
PLATFORMS = ["production", "staging", "mobile", "web app", "Chrome", "Firefox", "Safari", "AWS", "Azure", "GCP"]
ISSUES = ["a null reference error", "unexpected behavior", "data corruption", "performance degradation", "UI freeze", "authentication failure", "timeout exception"]
IMPACTS = ["all users", "premium tier users", "the admin panel", "mobile users", "the reporting module", "new signups", "API consumers"]

# Duration distributions per category+priority (realistic)
DURATION_MAP = {
    ("Bug", "Highest"): (10, 15),
    ("Bug", "High"): (12, 20),
    ("Bug", "Medium"): (14, 25),
    ("Bug", "Low"): (15, 30),
    ("Feature", "Highest"): (20, 35),
    ("Feature", "High"): (25, 45),
    ("Feature", "Medium"): (30, 55),
    ("Feature", "Low"): (35, 70),
    ("Task", "Highest"): (10, 18),
    ("Task", "High"): (12, 22),
    ("Task", "Medium"): (14, 28),
    ("Task", "Low"): (15, 35),
    ("Design", "Highest"): (12, 20),
    ("Design", "High"): (15, 28),
    ("Design", "Medium"): (18, 35),
    ("Design", "Low"): (20, 42),
    ("Frontend", "Highest"): (14, 22),
    ("Frontend", "High"): (18, 30),
    ("Frontend", "Medium"): (20, 38),
    ("Frontend", "Low"): (22, 45),
    ("Backend", "Highest"): (15, 25),
    ("Backend", "High"): (20, 35),
    ("Backend", "Medium"): (25, 45),
    ("Backend", "Low"): (28, 55),
    ("Devops", "Highest"): (12, 20),
    ("Devops", "High"): (15, 25),
    ("Devops", "Medium"): (18, 32),
    ("Devops", "Low"): (20, 40),
    ("Docs", "Highest"): (10, 15),
    ("Docs", "High"): (12, 20),
    ("Docs", "Medium"): (14, 25),
    ("Docs", "Low"): (15, 30),
}

# Priority weights (Highest tasks are rarer)
PRIORITIES = ["Low", "Medium", "High", "Highest"]
PRIORITY_WEIGHTS = [0.25, 0.35, 0.25, 0.15]

# Category weights
CATEGORIES = ["Task", "Feature", "Bug", "Design", "Frontend", "Backend", "Devops", "Docs"]
CATEGORY_WEIGHTS = [0.15, 0.18, 0.18, 0.08, 0.13, 0.13, 0.08, 0.07]

STATUSES = ["To Do", "In Progress", "Done", "In Review"]
STATUS_WEIGHTS = [0.30, 0.30, 0.25, 0.15]


def fill_template(template, category):
    return template.format(
        module=random.choice(MODULES),
        feature=random.choice(FEATURES),
        action=random.choice(ACTIONS),
        platform=random.choice(PLATFORMS),
        issue=random.choice(ISSUES),
        impact=random.choice(IMPACTS),
    )


def generate_dataset(n_samples=3000):
    records = []
    
    for i in range(n_samples):
        category = np.random.choice(CATEGORIES, p=CATEGORY_WEIGHTS)
        priority = np.random.choice(PRIORITIES, p=PRIORITY_WEIGHTS)
        status = np.random.choice(STATUSES, p=STATUS_WEIGHTS)
        
        # Generate title
        title_template = random.choice(TEMPLATES[category]["titles"])
        title = fill_template(title_template, category)
        
        # Generate description
        desc_template = random.choice(TEMPLATES[category]["descriptions"])
        description = fill_template(desc_template, category)
        
        # Generate duration
        min_d, max_d = DURATION_MAP[(category, priority)]
        duration = np.random.randint(min_d, max_d + 1)
        
        # Generate dates
        created = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 500))
        due = created + timedelta(days=duration)
        
        # Story points correlated with duration
        story_points = max(1, min(13, int(duration / 5) + random.randint(-1, 2)))
        
        records.append({
            "issue_id": f"PROJ-{1000 + i}",
            "title": title,
            "description": description,
            "issue_type": category,
            "priority": priority,
            "status": status,
            "story_points": story_points,
            "duration_days": duration,
            "created_date": created.strftime("%Y-%m-%d"),
            "due_date": due.strftime("%Y-%m-%d"),
            "assignee": f"user_{random.randint(1, 20)}",
            "project": f"Project-{random.choice(['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta'])}",
        })
    
    df = pd.DataFrame(records)
    return df


if __name__ == "__main__":
    df = generate_dataset(3000)
    df.to_csv("Machine_Learning/data/jira_issues_dataset.csv", index=False)
    print(f"Dataset generated: {df.shape}")
    print(f"\nCategory distribution:\n{df['issue_type'].value_counts()}")
    print(f"\nPriority distribution:\n{df['priority'].value_counts()}")
    print(f"\nDuration stats:\n{df['duration_days'].describe()}")
