import os
from core import create_app, db, migrate # Importa migrate también

app = create_app(os.getenv("FLASK_ENV", "development"))

# Esto asegura que el comando 'flask db' sea reconocido siempre
with app.app_context():
    if db.engine.url.drivername == "postgresql":
        # Opcional: configuraciones específicas de Postgres si fueran necesarias
        pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
