# MaajiKids Backend v3.0 — Guía de Despliegue
## Supabase (PostgreSQL) + Render.com

---

## 1. SUPABASE — Base de datos PostgreSQL

### 1.1 Crear proyecto en Supabase

1. Ir a https://supabase.com → **New project**
2. Elegir nombre: `maajikids` | Región: **South America (São Paulo)** | Contraseña fuerte
3. Esperar ~2 min a que el proyecto se active

### 1.2 Obtener la cadena de conexión

1. Dashboard → **Settings → Database**
2. Bajar hasta **Connection string**
3. Seleccionar modo **Session mode** (puerto 5432)
4. Copiar la URI — luce así:
   ```
   postgresql://postgres:[TU_PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
   ```
5. Guardar en `.env` como `DATABASE_URL`

> **Nota Supabase:** Reemplaza `postgres://` por `postgresql://` si la URI empieza con `postgres://`
> (el código lo hace automáticamente en `config.py`).

### 1.3 Ejecutar migraciones (primera vez)

```bash
# Local con tu .env configurado:
flask db init        # Solo la primera vez
flask db migrate -m "Initial schema"
flask db upgrade
```

En Render.com se ejecuta automáticamente (ver sección 3).

---

## 2. CLOUDINARY — Almacenamiento de imágenes

1. Registrarse en https://cloudinary.com (free tier: 25GB)
2. Dashboard → **API Keys** → copiar:
   - Cloud Name
   - API Key
   - API Secret
3. Agregar al `.env`:
   ```
   CLOUDINARY_CLOUD_NAME=tu_cloud_name
   CLOUDINARY_API_KEY=tu_api_key
   CLOUDINARY_API_SECRET=tu_api_secret
   ```

---

## 3. RENDER.COM — Backend Flask

### 3.1 Conectar repositorio

1. Ir a https://render.com → **New → Web Service**
2. Conectar tu repositorio de GitHub con el proyecto
3. Configurar:
   - **Name:** `maajikids-backend`
   - **Region:** Oregon (o la más cercana)
   - **Branch:** `main`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn manage:app`

### 3.2 Variables de entorno en Render

En el panel de Render → **Environment** → agregar:

| Variable | Valor |
|---|---|
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | (genera con `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `JWT_SECRET_KEY` | (otro token seguro) |
| `DATABASE_URL` | (cadena de Supabase) |
| `FERNET_KEY` | (genera con `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `CLOUDINARY_CLOUD_NAME` | tu valor |
| `CLOUDINARY_API_KEY` | tu valor |
| `CLOUDINARY_API_SECRET` | tu valor |
| `MP_ACCESS_TOKEN` | tu token de MercadoPago |
| `MP_WEBHOOK_SECRET` | tu webhook secret de MP |
| `MP_SUCCESS_URL` | `https://tu-frontend.com/pagos/exito` |
| `MP_FAILURE_URL` | `https://tu-frontend.com/pagos/fallo` |
| `MP_PENDING_URL` | `https://tu-frontend.com/pagos/pendiente` |
| `GEMINI_API_KEY` | tu API key de Google AI |
| `FRONTEND_URL` | `https://tu-frontend.com` |
| `APP_BASE_URL` | `https://maajikids-backend.onrender.com` |

### 3.3 Migraciones automáticas en Render

En Render → **Settings → Pre-Deploy Command:**
```
flask db upgrade
```

Esto ejecuta las migraciones antes de cada deploy.

---

## 4. MERCADOPAGO — Configurar Webhook

1. Ir a https://www.mercadopago.com.pe/developers/panel
2. **Webhooks → Agregar**
3. URL: `https://maajikids-backend.onrender.com/api/v1/payments/webhook`
4. Eventos: seleccionar `payment`
5. Copiar el **Webhook Secret** → agregar a `MP_WEBHOOK_SECRET`

---

## 5. GEMINI API KEY

1. Ir a https://aistudio.google.com/app/apikey
2. **Create API Key**
3. Agregar a `GEMINI_API_KEY` en `.env` y en Render

---

## 6. FLUJO DE ADMINISTRACIÓN — Cómo registrar datos

### 6.1 Primer uso (setup inicial)

```bash
# 1. Crear el primer admin directamente en Supabase SQL Editor:
# Ir a Supabase → SQL Editor → ejecutar:

INSERT INTO users (email, password_hash, role, first_name, last_name, is_active)
VALUES (
  'director@maajikids.com',
  '$2b$12$HASH_GENERADO',  -- Ver nota abajo
  'admin',
  'Director',
  'MaajiKids',
  true
);
```

O más fácil: usa el endpoint de registro con rol admin via Postman:
```bash
POST /api/v1/auth/register
# Luego cambia el role a 'admin' desde Supabase Table Editor
```

### 6.2 Flujo de creación de profesores (Teacher)

```
Admin → POST /api/v1/users/ → { role: "teacher", email, password, first_name, last_name }
```

### 6.3 Flujo de creación de talleres

```
Admin → POST /api/v1/workshops/ (multipart/form-data)
  → Campos: title, description, teacher_id, schedule, max_capacity, price, image (archivo)
```

### 6.4 Flujo completo del padre

```
1. POST /auth/register → obtiene access_token
2. POST /children/     → registra hijo (fecha_nacimiento ≤ 6 años)
3. GET  /workshops/    → ve talleres disponibles
4. POST /payments/create-preference → obtiene URL de MercadoPago
5. Paga en MercadoPago → webhook activa inscripción automáticamente
6. GET  /children/:id/evaluations  → ve evaluaciones de su hijo
7. POST /ia/chat       → habla con Maaji
```

### 6.5 Flujo de evaluación (Teacher)

```
1. GET  /workshops/:id/children → ver niños inscritos
2. POST /evaluations/ → registrar evaluación (puntajes 1-10)
3. POST /ia/recommendations/generate → generar recomendaciones IA
4. GET  /ia/recommendations/:id → ver recomendaciones generadas
```

### 6.6 Responder mensajes de contacto (Admin/Secretary)

```
1. GET  /contact/         → listar mensajes (muestra badge de no leídos)
2. GET  /contact/:id      → abrir mensaje (se marca como leído automáticamente)
3. POST /contact/:id/reply → { reply_body: "Texto de respuesta" }
   → La respuesta queda guardada en BD con quién respondió y cuándo
```

### 6.7 Generar reportes PDF

```
GET /api/v1/reports/evaluation/:id   → PDF evaluación + recomendaciones IA
GET /api/v1/reports/payments         → PDF historial de pagos (?status=approved)
GET /api/v1/reports/enrollments      → PDF inscripciones (?workshop_id=1)
GET /api/v1/reports/child/:id        → PDF expediente completo del niño
GET /api/v1/reports/dashboard        → PDF resumen del centro (solo admin)
```

---

## 7. ROLES — Tabla de permisos rápida

| Acción | Admin | Teacher | Secretary | Parent |
|---|:---:|:---:|:---:|:---:|
| Crear usuarios | ✅ | ❌ | ❌ | ❌ |
| Gestionar talleres | ✅ | ❌ | ❌ | ❌ |
| Ver todos los niños | ✅ | Solo sus talleres | ✅ | Solo sus hijos |
| Registrar evaluaciones | ✅ | ✅ | ❌ | ❌ |
| Generar IA | ✅ | ✅ | ❌ | ❌ |
| Ver recomendaciones | ✅ | ✅ | ❌ | ✅ (visibles) |
| Ver pagos | ✅ | ❌ | ✅ | Solo propios |
| Responder contacto | ✅ | ❌ | ✅ | ❌ |
| Enviar mensaje contacto | ✅ | ❌ | ❌ | ✅ (o sin auth) |
| Chat Maaji | ❌ | ❌ | ❌ | ✅ |
| Reportes PDF | ✅ | Evaluación/Niño | Pagos/Inscripciones | Evaluación/Niño propio |
| Control visibilidad IA | ✅ | ❌ | ❌ | ❌ |

---

## 8. SWAGGER UI

Con el servidor corriendo:
- **Local:** http://localhost:5000/apidocs/
- **Producción:** https://maajikids-backend.onrender.com/apidocs/

---

## 9. RESTRICCIONES IMPORTANTES

- **Edad máxima de niños:** 6 años (validado en `CreateChildSchema`)
- **Acceso sin login:** Solo el endpoint `POST /contact/` permite envío sin autenticación
- **Datos médicos:** `medical_info` y `allergies` siempre cifrados con AES-256 (Fernet)
- **Imágenes:** Máximo 5MB, se suben a Cloudinary, se entregan como WebP optimizado
- **Rate limiting:** 100 req/min por IP general; 20/min en login; 10/min en registro
