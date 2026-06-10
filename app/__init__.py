import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()

AUTH_MESSAGE = (
    '\u0414\u043b\u044f \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f \u0434\u0430\u043d\u043d\u043e\u0433\u043e \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f '
    '\u043d\u0435\u043e\u0431\u0445\u043e\u0434\u0438\u043c\u043e \u043f\u0440\u043e\u0439\u0442\u0438 \u043f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0443 \u0430\u0443\u0442\u0435\u043d\u0442\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u0438'
)


def create_app(config_object='config.Config'):
    app = Flask(__name__)
    app.config.from_object(config_object)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = AUTH_MESSAGE
    login_manager.login_message_category = 'warning'

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.auth import bp as auth_bp
    from app.books import bp as books_bp
    from app.stats import bp as stats_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(stats_bp)

    from app.utils import render_markdown

    app.jinja_env.filters['markdown'] = render_markdown

    @app.cli.command('init-db')
    def init_db():
        """Create all database tables."""
        db.create_all()
        print('Tables created.')

    @app.cli.command('seed')
    def seed():
        """Insert roles, genres and test users."""
        from app.seed import seed_data
        seed_data()

    return app
