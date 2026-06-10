import csv
import io
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, render_template, request
from sqlalchemy import func, select

from app import db
from app.models import Book, VisitLog
from app.utils import roles_required

bp = Blueprint('stats', __name__, url_prefix='/stats')

PER_PAGE = 10

ANONYMOUS_NAME = (
    '\u041d\u0435\u0430\u0443\u0442\u0435\u043d\u0442\u0438\u0444\u0438\u0446\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439 '
    '\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c'
)


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except (TypeError, ValueError):
        return None


def _journal_stmt():
    return select(VisitLog).order_by(
        VisitLog.created_at.desc(), VisitLog.id.desc()
    )


def _books_stats_stmt(date_from, date_to):
    """Views per book, authenticated users only, optional date range."""
    stmt = (
        select(Book.title, func.count(VisitLog.id).label('views'))
        .join(VisitLog, VisitLog.book_id == Book.id)
        .where(VisitLog.user_id.isnot(None))
    )
    if date_from:
        stmt = stmt.where(VisitLog.created_at >= date_from)
    if date_to:
        # date_to is inclusive
        stmt = stmt.where(VisitLog.created_at < date_to + timedelta(days=1))
    return stmt.group_by(Book.id, Book.title).order_by(
        func.count(VisitLog.id).desc()
    )


@bp.route('/')
@roles_required('administrator')
def index():
    tab = request.args.get('tab', 'journal')
    if tab not in ('journal', 'books'):
        tab = 'journal'
    page = request.args.get('page', 1, type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if tab == 'books':
        # db.paginate scalarizes rows, so paginate Book entities ordered by view
        # count and attach the per-book counts for the current page afterwards.
        df = _parse_date(date_from)
        dt = _parse_date(date_to)
        stmt = (
            select(Book)
            .join(VisitLog, VisitLog.book_id == Book.id)
            .where(VisitLog.user_id.isnot(None))
        )
        if df:
            stmt = stmt.where(VisitLog.created_at >= df)
        if dt:
            stmt = stmt.where(VisitLog.created_at < dt + timedelta(days=1))
        stmt = stmt.group_by(Book.id).order_by(func.count(VisitLog.id).desc())
        pagination = db.paginate(
            stmt, page=page, per_page=PER_PAGE, error_out=False
        )
        page_ids = [book.id for book in pagination.items]
        counts = {}
        if page_ids:
            cstmt = select(
                VisitLog.book_id, func.count(VisitLog.id)
            ).where(
                VisitLog.user_id.isnot(None), VisitLog.book_id.in_(page_ids)
            )
            if df:
                cstmt = cstmt.where(VisitLog.created_at >= df)
            if dt:
                cstmt = cstmt.where(VisitLog.created_at < dt + timedelta(days=1))
            counts = dict(
                db.session.execute(cstmt.group_by(VisitLog.book_id)).all()
            )
        for book in pagination.items:
            book.views = counts.get(book.id, 0)
    else:
        stmt = _journal_stmt()
        pagination = db.paginate(
            stmt, page=page, per_page=PER_PAGE, error_out=False
        )

    return render_template(
        'stats/index.html',
        tab=tab,
        pagination=pagination,
        date_from=date_from,
        date_to=date_to,
        anonymous_name=ANONYMOUS_NAME,
        per_page=PER_PAGE,
    )


def _csv_response(output, filename):
    # BOM so that Excel opens UTF-8 correctly
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@bp.route('/journal/export')
@roles_required('administrator')
def export_journal():
    logs = db.session.execute(_journal_stmt()).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        '\u2116',
        '\u0424\u0418\u041e \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f',
        '\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043a\u043d\u0438\u0433\u0438',
        '\u0414\u0430\u0442\u0430 \u0438 \u0432\u0440\u0435\u043c\u044f \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430',
    ])
    for index, log in enumerate(logs, start=1):
        writer.writerow([
            index,
            log.user.full_name if log.user else ANONYMOUS_NAME,
            log.book.title if log.book else '',
            log.created_at.strftime('%d.%m.%Y %H:%M:%S'),
        ])

    filename = f'visit_journal_{date.today().isoformat()}.csv'
    return _csv_response(output, filename)


@bp.route('/books/export')
@roles_required('administrator')
def export_books_stats():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    rows = db.session.execute(
        _books_stats_stmt(_parse_date(date_from), _parse_date(date_to))
    ).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        '\u2116',
        '\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043a\u043d\u0438\u0433\u0438',
        '\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u043e\u0432',
    ])
    for index, (title, views) in enumerate(rows, start=1):
        writer.writerow([index, title, views])

    filename = f'books_stats_{date.today().isoformat()}.csv'
    return _csv_response(output, filename)
