from flask_login import UserMixin
from sqlalchemy.dialects.mysql import YEAR
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)

    users = db.relationship('User', back_populates='role')


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))
    role_id = db.Column(
        db.Integer, db.ForeignKey('roles.id'), nullable=False
    )

    role = db.relationship('Role', back_populates='users')
    reviews = db.relationship('Review', back_populates='user')

    @property
    def full_name(self):
        return ' '.join(
            part for part in (self.last_name, self.first_name, self.middle_name) if part
        )

    @property
    def is_admin(self):
        return self.role.name == 'administrator'

    @property
    def is_moderator(self):
        return self.role.name == 'moderator'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


book_genres = db.Table(
    'book_genres',
    db.Column(
        'book_id',
        db.Integer,
        db.ForeignKey('books.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    db.Column(
        'genre_id',
        db.Integer,
        db.ForeignKey('genres.id', ondelete='CASCADE'),
        primary_key=True,
    ),
)


class Genre(db.Model):
    __tablename__ = 'genres'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    short_description = db.Column(db.Text, nullable=False)
    year = db.Column(YEAR, nullable=False)
    publisher = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    pages = db.Column(db.Integer, nullable=False)

    genres = db.relationship('Genre', secondary=book_genres, backref='books')
    cover = db.relationship(
        'Cover',
        back_populates='book',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    reviews = db.relationship(
        'Review',
        back_populates='book',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )


class Cover(db.Model):
    __tablename__ = 'covers'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    md5_hash = db.Column(db.String(32), nullable=False, index=True)
    book_id = db.Column(
        db.Integer,
        db.ForeignKey('books.id', ondelete='CASCADE'),
        nullable=False,
    )

    book = db.relationship('Book', back_populates='cover')


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(
        db.Integer,
        db.ForeignKey('books.id', ondelete='CASCADE'),
        nullable=False,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.TIMESTAMP, nullable=False, server_default=db.func.current_timestamp()
    )

    book = db.relationship('Book', back_populates='reviews')
    user = db.relationship('User', back_populates='reviews')


class VisitLog(db.Model):
    __tablename__ = 'visit_logs'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(
        db.Integer,
        db.ForeignKey('books.id', ondelete='CASCADE'),
        nullable=False,
    )
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    session_id = db.Column(db.String(64), index=True)
    created_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        server_default=db.func.current_timestamp(),
        index=True,
    )

    book = db.relationship('Book')
    user = db.relationship('User')
