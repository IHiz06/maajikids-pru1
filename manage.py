import os
from core import create_app, db # Asegúrate de exportar 'db' desde tu carpeta core
from flask_migrate import Migrate

app = create_app(os.getenv("FLASK_ENV", "development"))

# Esta línea es la que soluciona el error "No such command 'db'"
migrate = Migrate(app, db)

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False), host="0.0.0.0", port=5000)
