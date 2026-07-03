from app import create_app
from app.extensions import db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass  # Tables already exist
    app.run(debug=True, port=5000)
