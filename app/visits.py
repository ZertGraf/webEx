import uuid
from datetime import datetime, timedelta

from flask import session
from flask_login import current_user
from sqlalchemy import func

from app import db
from app.models import Book, VisitLog

DAILY_LIMIT = 10
POPULAR_PERIOD_DAYS = 90
TOP_COUNT = 5


def _session_id(create=True):
    if 'visitor_id' not in session:
        if not create:
            return None
        session['visitor_id'] = uuid.uuid4().hex
    return session['visitor_id']


def log_visit(book):
    """Register a book page view, max 10 per visitor per book per day."""
    user_id = current_user.id if current_user.is_authenticated else None
    sid = _session_id()

    today_start = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    query = VisitLog.query.filter(
        VisitLog.book_id == book.id, VisitLog.created_at >= today_start
    )
    if user_id is not None:
        query = query.filter(VisitLog.user_id == user_id)
    else:
        query = query.filter(
            VisitLog.user_id.is_(None), VisitLog.session_id == sid
        )
    if query.count() >= DAILY_LIMIT:
        return

    try:
        db.session.add(
            VisitLog(book_id=book.id, user_id=user_id, session_id=sid)
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


def popular_books(limit=TOP_COUNT):
    """Top viewed books for the last 3 months: [(Book, views), ...]."""
    since = datetime.now() - timedelta(days=POPULAR_PERIOD_DAYS)
    return (
        db.session.query(Book, func.count(VisitLog.id).label('views'))
        .join(VisitLog, VisitLog.book_id == Book.id)
        .filter(VisitLog.created_at >= since)
        .group_by(Book.id)
        .order_by(func.count(VisitLog.id).desc())
        .limit(limit)
        .all()
    )


def recent_books(limit=TOP_COUNT):
    """Books recently viewed by the current visitor, newest first."""
    user_id = current_user.id if current_user.is_authenticated else None
    sid = _session_id(create=False)
    if user_id is None and sid is None:
        return []

    query = db.session.query(
        VisitLog.book_id, func.max(VisitLog.created_at).label('last_visit')
    )
    if user_id is not None:
        query = query.filter(VisitLog.user_id == user_id)
    else:
        query = query.filter(
            VisitLog.user_id.is_(None), VisitLog.session_id == sid
        )
    rows = (
        query.group_by(VisitLog.book_id)
        .order_by(func.max(VisitLog.created_at).desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return []

    books = {
        book.id: book
        for book in Book.query.filter(
            Book.id.in_([row.book_id for row in rows])
        )
    }
    return [books[row.book_id] for row in rows if row.book_id in books]
