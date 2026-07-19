"""Description templates for project and task suggestions."""

import random


def _pick_template(templates, category, text, priority, duration_days):
    template = random.choice(templates)
    return template.format(category=category, text=text[:60], priority=priority, duration_days=duration_days)


def project_description(category: str, text: str, priority: str, duration_days: int) -> str:
    templates = [
        "{category} initiative: {text}. With {priority} priority over {duration_days} days, this project covers discovery, iteration, and delivery.",
        "A {category.lower()} project focused on {text}. Priority: {priority}. Estimated timeline: {duration_days} days including review cycles.",
        "This {duration_days}-day {category} effort addresses: {text}. Planned with {priority} priority across design, build, and test phases.",
    ]
    return _pick_template(templates, category, text, priority, duration_days)


def task_description(category: str, text: str, priority: str, duration_days: int) -> str:
    templates = [
        "Complete {category.lower()} task: {text[:80]}. Priority {priority}, estimated {duration_days} days. Steps: scope, implement, verify, close.",
        "{category} — {text[:80]}. Effort: {duration_days}d, Priority: {priority}. Deliverable includes documentation and tests.",
        "Implement {category.lower()} work for: {text[:80]}. Target: {duration_days} days, {priority} priority. Define requirements, build, QA, ship.",
    ]
    return _pick_template(templates, category, text, priority, duration_days)


def fallback_description(kind: str) -> str:
    if kind == 'project':
        return "A new project initiative. Please add a title and description for more tailored suggestions."
    return "A new task item. Add a title and description to receive detailed recommendations."
