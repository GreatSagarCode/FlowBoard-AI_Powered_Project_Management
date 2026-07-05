from flask import Flask
from config import Config
from app.extensions import db, login_manager

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask extensions here
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints here
    from app.auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main.routes import bp as main_bp
    app.register_blueprint(main_bp)

    from app.projects.routes import bp as projects_bp
    app.register_blueprint(projects_bp, url_prefix='/projects')

    from app.tasks.routes import bp as tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/tasks')

    from app.organizations import bp as organizations_bp
    app.register_blueprint(organizations_bp, url_prefix='/organizations')

    from app.docs.routes import bp as docs_bp
    app.register_blueprint(docs_bp, url_prefix='/docs')
    
    # Import models so they are registered with SQLAlchemy
    from app import models

    with app.app_context():
        db.create_all()

    # Pre-load ML models to eliminate cold-start latency on first prediction
    from app.ml.inference import load_models
    load_models()

    return app
