from app import db
from app.models import Genre, Role, User


def seed_data():
    if Role.query.first():
        print('Database already seeded.')
        return

    admin_role = Role(
        name='administrator',
        description=(
            '\u0421\u0443\u043f\u0435\u0440\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c, \u0438\u043c\u0435\u0435\u0442 \u043f\u043e\u043b\u043d\u044b\u0439 \u0434\u043e\u0441\u0442\u0443\u043f '
            '\u043a \u0441\u0438\u0441\u0442\u0435\u043c\u0435, \u0432 \u0442\u043e\u043c \u0447\u0438\u0441\u043b\u0435 \u043a \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u044e \u0438 \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u044e \u043a\u043d\u0438\u0433'
        ),
    )
    moderator_role = Role(
        name='moderator',
        description=(
            '\u041c\u043e\u0436\u0435\u0442 \u0440\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0434\u0430\u043d\u043d\u044b\u0435 \u043a\u043d\u0438\u0433 '
            '\u0438 \u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0438\u0442\u044c \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u044e \u0440\u0435\u0446\u0435\u043d\u0437\u0438\u0439'
        ),
    )
    user_role = Role(
        name='user',
        description='\u041c\u043e\u0436\u0435\u0442 \u043e\u0441\u0442\u0430\u0432\u043b\u044f\u0442\u044c \u0440\u0435\u0446\u0435\u043d\u0437\u0438\u0438',
    )

    genres = [
        Genre(name=name)
        for name in (
            '\u0424\u0430\u043d\u0442\u0430\u0441\u0442\u0438\u043a\u0430',
            '\u0424\u044d\u043d\u0442\u0435\u0437\u0438',
            '\u0414\u0435\u0442\u0435\u043a\u0442\u0438\u0432',
            '\u0420\u043e\u043c\u0430\u043d',
            '\u041f\u043e\u044d\u0437\u0438\u044f',
            '\u041f\u0440\u0438\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f',
            '\u0418\u0441\u0442\u043e\u0440\u0438\u044f',
            '\u041d\u0430\u0443\u0447\u043d\u043e-\u043f\u043e\u043f\u0443\u043b\u044f\u0440\u043d\u043e\u0435',
        )
    ]

    db.session.add_all([admin_role, moderator_role, user_role, *genres])
    db.session.flush()

    users = [
        User(
            login='admin',
            last_name='\u0410\u0434\u043c\u0438\u043d\u043e\u0432',
            first_name='\u0410\u0434\u043c\u0438\u043d',
            middle_name='\u0410\u0434\u043c\u0438\u043d\u043e\u0432\u0438\u0447',
            role_id=admin_role.id,
        ),
        User(
            login='moderator',
            last_name='\u041c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440\u043e\u0432',
            first_name='\u041c\u043e\u0434\u0435\u0440\u0430\u0442\u043e\u0440',
            role_id=moderator_role.id,
        ),
        User(
            login='user',
            last_name='\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0432',
            first_name='\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c',
            role_id=user_role.id,
        ),
    ]
    passwords = ['Admin123!', 'Moder123!', 'User123!']
    for user, password in zip(users, passwords):
        user.set_password(password)

    db.session.add_all(users)
    db.session.commit()
    print('Seed data inserted. Users: admin/Admin123!, moderator/Moder123!, user/User123!')
