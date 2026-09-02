from django import template
from core.media import media_available as media_file_available

register = template.Library()


@register.filter(name='has_portal_permission')
def has_portal_permission(user, permission_code):
    """Template companion to the central server-side permission checker."""
    return bool(getattr(user, 'is_authenticated', False) and user.has_portal_permission(permission_code))

@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Template tag to preserve existing GET parameters while modifying specified query parameters.
    Example usage in pagination: <a href="?{% query_transform page=page_obj.next_page_number %}">Next</a>
    """
    request = context.get('request')
    if not request:
        return ''
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is not None and value != '':
            query[key] = value
        elif key in query:
            del query[key]
    return query.urlencode()


@register.filter
def media_available(field_file):
    """Return whether an uploaded file is still present in its storage backend.

    File records can outlive the object in storage after a manual cleanup or a
    failed deployment.  Templates use this before rendering media URLs so users
    see a clear empty state instead of a broken image or storage error.
    """
    return media_file_available(field_file)
