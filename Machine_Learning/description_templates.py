"""Fake AI description templates for project and task suggestions."""


def project_description(category: str, text: str, priority: str, duration_days: int) -> str:
    return (
        f"Project {category} focused on {text[:60]}."
        f"\n\nThis project aims to deliver the specified requirements with a {priority} priority "
        f"over an estimated {duration_days} days timeline. Key milestones include planning, "
        f"execution, and review phases to ensure high-quality delivery."
    )


def task_description(category: str, text: str, priority: str, duration_days: int) -> str:
    return (
        f"<h4>Objective</h4><p>Implement the {category.lower()} related to: "
        f"<strong>{text[:80]}...</strong></p>"
        f"<h4>Requirements</h4><ul><li>Gather detailed specifications.</li>"
        f"<li>Complete necessary technical or design steps.</li>"
        f"<li>Perform testing and QA.</li></ul>"
        f"<h4>Constraints</h4><p>Priority: {priority} | Estimated effort: {duration_days} days</p>"
    )


def fallback_description(kind: str) -> str:
    if kind == "project":
        return "Please provide more details."
    return "<p>Please provide more details.</p>"
