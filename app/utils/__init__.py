"""Utility functions — get_membership helper with per-request caching."""
from flask import g
from flask_login import current_user

def get_membership(organization_id=None):
    if not current_user.is_authenticated:
        return None
    from flask import session
    active_org_id = organization_id or session.get('active_org_id')
    if not active_org_id:
        return None
    cache_key = f'membership_{active_org_id}'
    if hasattr(g, cache_key):
        return getattr(g, cache_key)
    from app.models import Membership
    membership = Membership.query.filter_by(
        user_id=current_user.id,
        organization_id=active_org_id
    ).first()
    setattr(g, cache_key, membership)
    return membership
