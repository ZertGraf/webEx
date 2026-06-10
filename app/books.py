import hashlib
import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app import db
from app.models import Book, Cover, Genre, Review
from app.utils import roles_required, sanitize
from app.visits import log_visit, popular_books, recent_books

bp = Blueprint('books', __name__)

PER_PAGE = 10

SAVE_ERROR = (
    '\u041f\u0440\u0438 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0438 \u0434\u0430\u043d\u043d\u044b\u0445 \u0432\u043e\u0437\u043d\u0438\u043a\u043b\u0430 \u043e\u0448\u0438\u0431\u043a\u0430. '
    '\u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u043e\u0441\u0442\u044c \u0432\u0432\u0435\u0434\u0451\u043d\u043d\u044b\u0445 \u0434\u0430\u043d\u043d\u044b\u0445.'
)

RATINGS = [
    (5, '\u043e\u0442\u043b\u0438\u0447\u043d\u043e'),
    (4, '\u0445\u043e\u0440\u043e\u0448\u043e'),
    (3, '\u0443\u0434\u043e\u0432\u043b\u0435\u0442\u0432\u043e\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u043e'),
    (2, '\u043d\u0435\u0443\u0434\u043e\u0432\u043b\u0435\u0442\u0432\u043e\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u043e'),
    (1, '\u043f\u043b\u043e\u0445\u043e'),
    (0, '\u0443\u0436\u0430\u0441\u043d\u043e'),
]


@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    # db.paginate scalarizes the result, so paginate over Book entities only and
    # attach aggregate rating/count for the current page in a second query.
    pagination = db.paginate(
        select(Book).order_by(Book.year.desc(), Book.id.desc()),
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    book_ids = [book.id for book in pagination.items]
    stats = {}
    if book_ids:
        rows = db.session.execute(
            select(
                Review.book_id,
                func.avg(Review.rating),
                func.count(Review.id),
            )
            .where(Review.book_id.in_(book_ids))
            .group_by(Review.book_id)
        ).all()
        stats = {book_id: (avg, count) for book_id, avg, count in rows}
    for book in pagination.items:
        book.avg_rating, book.reviews_count = stats.get(book.id, (None, 0))

    return render_template(
        'index.html',
        pagination=pagination,
        popular=popular_books(),
        recent=recent_books(),
    )


@bp.route('/media/covers/<path:filename>')
def cover_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


def _form_data():
    return {
        'title': request.form.get('title', '').strip(),
        'short_description': request.form.get('short_description', '').strip(),
        'year': request.form.get('year', '').strip(),
        'publisher': request.form.get('publisher', '').strip(),
        'author': request.form.get('author', '').strip(),
        'pages': request.form.get('pages', '').strip(),
        'genre_ids': [int(i) for i in request.form.getlist('genres')],
    }


def _apply_to_book(book, data):
    required = ('title', 'short_description', 'year', 'publisher', 'author', 'pages')
    if not all(data[field] for field in required) or not data['genre_ids']:
        raise ValueError('missing required fields')

    book.title = data['title']
    book.short_description = sanitize(data['short_description'])
    book.year = int(data['year'])
    book.publisher = data['publisher']
    book.author = data['author']
    book.pages = int(data['pages'])

    genres = Genre.query.filter(Genre.id.in_(data['genre_ids'])).all()
    if not genres:
        raise ValueError('genres not found')
    book.genres = genres


@bp.route('/books/new', methods=['GET', 'POST'])
@roles_required('administrator')
def create():
    genres = Genre.query.order_by(Genre.name).all()
    data = {'genre_ids': []}

    if request.method == 'POST':
        data = _form_data()
        file = request.files.get('cover')
        file_bytes = file.read() if file and file.filename else None
        try:
            if not file_bytes:
                raise ValueError('cover is required')

            book = Book()
            _apply_to_book(book, data)
            db.session.add(book)
            db.session.flush()

            md5_hash = hashlib.md5(file_bytes).hexdigest()
            existing = Cover.query.filter_by(md5_hash=md5_hash).first()
            ext = os.path.splitext(file.filename)[1].lower() or '.img'

            cover = Cover(
                filename='',
                mime_type=file.mimetype or 'application/octet-stream',
                md5_hash=md5_hash,
                book_id=book.id,
            )
            db.session.add(cover)
            db.session.flush()

            need_save_file = existing is None
            cover.filename = (
                existing.filename if existing else f'{cover.id}{ext}'
            )
            db.session.commit()

            # Save the file only after DB records are committed successfully.
            if need_save_file:
                path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'], cover.filename
                )
                with open(path, 'wb') as out:
                    out.write(file_bytes)

            return redirect(url_for('books.view', book_id=book.id))
        except Exception:
            db.session.rollback()
            flash(SAVE_ERROR, 'danger')

    return render_template(
        'books/create.html', genres=genres, data=data
    )


@bp.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@roles_required('administrator', 'moderator')
def edit(book_id):
    book = db.get_or_404(Book, book_id)
    genres = Genre.query.order_by(Genre.name).all()

    if request.method == 'POST':
        data = _form_data()
        try:
            _apply_to_book(book, data)
            db.session.commit()
            return redirect(url_for('books.view', book_id=book.id))
        except Exception:
            db.session.rollback()
            flash(SAVE_ERROR, 'danger')
    else:
        data = {
            'title': book.title,
            'short_description': book.short_description,
            'year': book.year,
            'publisher': book.publisher,
            'author': book.author,
            'pages': book.pages,
            'genre_ids': [g.id for g in book.genres],
        }

    return render_template(
        'books/edit.html', genres=genres, data=data, book=book
    )


@bp.route('/books/<int:book_id>')
def view(book_id):
    book = db.get_or_404(Book, book_id)
    log_visit(book)
    reviews = (
        Review.query.filter_by(book_id=book.id)
        .order_by(Review.created_at.desc())
        .all()
    )
    avg_rating = db.session.query(func.avg(Review.rating)).filter(
        Review.book_id == book.id
    ).scalar()

    user_review = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(
            book_id=book.id, user_id=current_user.id
        ).first()

    return render_template(
        'books/view.html',
        book=book,
        reviews=reviews,
        avg_rating=avg_rating,
        user_review=user_review,
    )


@bp.route('/books/<int:book_id>/delete', methods=['POST'])
@roles_required('administrator')
def delete(book_id):
    book = db.get_or_404(Book, book_id)
    title = book.title
    cover_filename = book.cover.filename if book.cover else None
    cover_md5 = book.cover.md5_hash if book.cover else None

    try:
        db.session.delete(book)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(SAVE_ERROR, 'danger')
        return redirect(url_for('books.index'))

    # Remove the cover file only if no other cover record uses the same file.
    if cover_filename and cover_md5:
        still_used = Cover.query.filter_by(md5_hash=cover_md5).count()
        if still_used == 0:
            path = os.path.join(
                current_app.config['UPLOAD_FOLDER'], cover_filename
            )
            if os.path.exists(path):
                os.remove(path)

    flash(
        f'\u041a\u043d\u0438\u0433\u0430 \u00ab{title}\u00bb \u0443\u0441\u043f\u0435\u0448\u043d\u043e \u0443\u0434\u0430\u043b\u0435\u043d\u0430.',
        'success',
    )
    return redirect(url_for('books.index'))


@bp.route('/books/<int:book_id>/review', methods=['GET', 'POST'])
@login_required
def create_review(book_id):
    book = db.get_or_404(Book, book_id)

    existing = Review.query.filter_by(
        book_id=book.id, user_id=current_user.id
    ).first()
    if existing:
        return redirect(url_for('books.view', book_id=book.id))

    data = {'rating': 5, 'text': ''}
    if request.method == 'POST':
        data = {
            'rating': request.form.get('rating', type=int),
            'text': request.form.get('text', '').strip(),
        }
        try:
            if data['rating'] is None or not 0 <= data['rating'] <= 5:
                raise ValueError('invalid rating')
            text = sanitize(data['text'])
            if not text:
                raise ValueError('empty text')

            review = Review(
                book_id=book.id,
                user_id=current_user.id,
                rating=data['rating'],
                text=text,
            )
            db.session.add(review)
            db.session.commit()
            return redirect(url_for('books.view', book_id=book.id))
        except Exception:
            db.session.rollback()
            flash(SAVE_ERROR, 'danger')

    return render_template(
        'reviews/form.html', book=book, ratings=RATINGS, data=data
    )
