from functools import wraps

import bleach
import markdown as md
from flask import flash, redirect, request, url_for
from flask_login import current_user
from markupsafe import Markup

from app import AUTH_MESSAGE

ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'em', 'h1', 'h2',
    'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'strong',
    'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
}

PERMISSION_MESSAGE = (
    '\u0423 \u0432\u0430\u0441 \u043d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u043f\u0440\u0430\u0432 '
    '\u0434\u043b\u044f \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f \u0434\u0430\u043d\u043d\u043e\u0433\u043e \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f'
)


def sanitize(text):
    """Escape dangerous tags in user supplied markdown text."""
    return bleach.clean(
        text or '', tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES
    )


def render_markdown(text):
    """Jinja filter: render sanitized markdown to HTML."""
    html = md.markdown(text or '', extensions=['extra'])
    return Markup(html)


def roles_required(*role_names):
    """Allow access only to authenticated users with one of the given roles."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash(AUTH_MESSAGE, 'warning')
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role.name not in role_names:
                flash(PERMISSION_MESSAGE, 'danger')
                return redirect(url_for('books.index'))
            return view(*args, **kwargs)

        return wrapped

    return decorator
