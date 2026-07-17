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
        f"Objective:\nImplement the {category.lower()} related to: {text[:80]}...\n\n"
        f"Requirements:\n- Gather detailed specifications.\n"
        f"- Complete necessary technical or design steps.\n"
        f"- Perform testing and QA.\n\n"
        f"Constraints:\nPriority: {priority} | Estimated effort: {duration_days} days"
    )


def fallback_description(kind: str) -> str:
    return "Please provide more details."
