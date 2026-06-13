"""Populate the catalogue with demo books, covers (fetched from OpenLibrary
with a solid-color fallback) and a few reviews. Exposed as `flask seed-books`
and invoked once on container start. Idempotent: a second run is a no-op."""
import hashlib
import json
import os
import struct
import time
import urllib.parse
import urllib.request
import zlib

from flask import current_app

from app import db
from app.models import Book, Cover, Genre, Review, User

UA = 'ZertGraf-elibrary-seed/1.0 (educational project)'
# keep network calls short so a slow OpenLibrary never stalls container start
COVER_TIMEOUT = 10

# (title, author, publisher, year, pages, [genres], openlibrary search query)
BOOKS = [
    ('Мастер и Маргарита', 'Булгаков М.А.', 'АСТ', 1967, 480,
     ['Роман', 'Фэнтези'], ('The Master and Margarita', 'Bulgakov')),
    ('Солярис', 'Лем С.', 'Мир', 1961, 320,
     ['Фантастика'], ('Solaris', 'Lem')),
    ('1984', 'Оруэлл Дж.', 'Secker & Warburg', 1949, 328,
     ['Фантастика', 'Роман'], ('1984', 'George Orwell')),
    ('Гарри Поттер и философский камень', 'Роулинг Дж.К.', 'Bloomsbury',
     1997, 332, ['Фэнтези', 'Приключения'],
     ('Harry Potter and the Philosopher\'s Stone', 'Rowling')),
    ('Сто лет одиночества', 'Маркес Г.Г.', 'Sudamericana', 1967, 417,
     ['Роман'], ('One Hundred Years of Solitude', 'Marquez')),
    ('Дюна', 'Герберт Ф.', 'Chilton Books', 1965, 412,
     ['Фантастика', 'Приключения'], ('Dune', 'Frank Herbert')),
    ('Краткая история времени', 'Хокинг С.', 'Bantam', 1988, 256,
     ['Научно-популярное'], ('A Brief History of Time', 'Hawking')),
    ('Тихий Дон', 'Шолохов М.А.', 'Художественная литература', 1928, 1500,
     ['Роман', 'История'], ('And Quiet Flows the Don', 'Sholokhov')),
    ('Над пропастью во ржи', 'Сэлинджер Дж.Д.', 'Little, Brown', 1951, 277,
     ['Роман'], ('The Catcher in the Rye', 'Salinger')),
    ('Великий Гэтсби', 'Фицджеральд Ф.С.', 'Scribner', 1925, 218,
     ['Роман'], ('The Great Gatsby', 'Fitzgerald')),
    ('Старик и море', 'Хемингуэй Э.', 'Scribner', 1952, 127,
     ['Роман', 'Приключения'], ('The Old Man and the Sea', 'Hemingway')),
    ('Задача трёх тел', 'Лю Цысинь', 'Chongqing', 2008, 302,
     ['Фантастика'], ('The Three-Body Problem', 'Liu Cixin')),
]

DESCRIPTION = (
    '# Краткое описание\n\n'
    'Это **выдающееся** произведение мировой литературы.\n\n'
    '- классика жанра\n- рекомендовано к прочтению\n\n'
    'Подробнее см. [Открытая библиотека](https://openlibrary.org).'
)


def _placeholder_png(seed, size=200):
    """Solid-color PNG fallback when a cover cannot be downloaded."""
    r, g, b = (seed * 37) % 256, (seed * 91) % 256, (seed * 53) % 256

    def chunk(typ, data):
        body = typ + data
        return (
            struct.pack('>I', len(data))
            + body
            + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
        )

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    raw = b''.join(b'\x00' + bytes([r, g, b]) * size for _ in range(size))
    return (
        sig + chunk(b'IHDR', ihdr)
        + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''),
        'image/png', '.png',
    )


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=COVER_TIMEOUT) as resp:
        return resp.read()


def fetch_cover(title, author, seed):
    """Return (bytes, mime_type, ext). Falls back to a placeholder PNG."""
    try:
        q = urllib.parse.urlencode({
            'title': title, 'author': author, 'limit': 5,
            'fields': 'cover_i,title',
        })
        data = json.loads(_get(f'https://openlibrary.org/search.json?{q}'))
        cover_id = next(
            (d['cover_i'] for d in data.get('docs', []) if d.get('cover_i')),
            None,
        )
        if cover_id:
            img = _get(
                f'https://covers.openlibrary.org/b/id/{cover_id}-L.jpg'
            )
            if img[:2] == b'\xff\xd8' and len(img) > 2000:  # valid JPEG
                return img, 'image/jpeg', '.jpg'
    except Exception as exc:  # noqa: BLE001
        print(f'  cover fetch failed for "{title}": {exc}')
    print(f'  using placeholder for "{title}"')
    return _placeholder_png(seed)


def seed_books():
    """Insert demo books once. Requires genres/users from `flask seed`."""
    if Book.query.first():
        print('Books already present, skipping.')
        return

    upload = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload, exist_ok=True)
    genres_by_name = {g.name: g for g in Genre.query.all()}

    created = []
    for i, (title, author, publisher, year, pages, gnames, query) in enumerate(BOOKS):
        print(f'[{i + 1}/{len(BOOKS)}] {title} — fetching cover…')
        img, mime, ext = fetch_cover(query[0], query[1], i + 1)

        book = Book(
            title=title, short_description=DESCRIPTION, year=year,
            publisher=publisher, author=author, pages=pages,
        )
        book.genres = [genres_by_name[n] for n in gnames if n in genres_by_name]
        db.session.add(book)
        db.session.flush()

        md5 = hashlib.md5(img).hexdigest()
        cover = Cover(
            filename='', mime_type=mime, md5_hash=md5, book_id=book.id
        )
        db.session.add(cover)
        db.session.flush()
        cover.filename = f'{cover.id}{ext}'
        with open(os.path.join(upload, cover.filename), 'wb') as f:
            f.write(img)
        created.append(book)
        time.sleep(0.2)  # be polite to the API

    db.session.commit()

    admin = User.query.filter_by(login='admin').first()
    moder = User.query.filter_by(login='moderator').first()
    if created and admin and moder:
        db.session.add_all([
            Review(book_id=created[0].id, user_id=admin.id, rating=5,
                   text='Великолепный роман. **Рекомендую.**'),
            Review(book_id=created[0].id, user_id=moder.id, rating=4,
                   text='Хорошая книга, читается на одном дыхании.'),
            Review(book_id=created[1].id, user_id=admin.id, rating=5,
                   text='Классика научной фантастики.'),
        ])
        db.session.commit()

    print(f'Inserted {len(created)} books with covers.')
