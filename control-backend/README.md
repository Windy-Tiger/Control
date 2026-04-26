# Control — Backend API

FastAPI + PostgreSQL backend for the Control transport management system.
Multi-tenant, JWT-authenticated, Railway-ready.

## API Endpoints

### Auth
- `POST /auth/login` — returns JWT token

### Viagens
- `GET /viagens/` — list (filter: `?concluido=false&fronteira=Luvo&q=search`)
- `GET /viagens/{id}` — single viagem with logs + veiculos
- `POST /viagens/` — create
- `PUT /viagens/{id}` — edit data (admin only, requires `reason`)
- `PUT /viagens/{id}/movimento` — toggle viagem/parado
- `POST /viagens/{id}/logs` — add update entry
- `PUT /viagens/{id}/logs/{log_id}` — edit log (admin only)
- `POST /viagens/{id}/concluir-luanda` — mark Luanda done
- `POST /viagens/{id}/concluir-fronteira` — mark frontier done (with stamp data)
- `POST /viagens/{id}/reactivar` — reopen closed viagem
- `DELETE /viagens/{id}` — delete (admin only)

### Photos
- `GET /viagens/{id}/photos?instance=saida` — list photos
- `POST /viagens/{id}/photos?instance=saida` — upload (multipart)
- `GET /viagens/{id}/photos/{photo_id}/file` — download file
- `DELETE /viagens/{id}/photos/{photo_id}` — delete

### Pedidos (edit requests)
- `GET /pedidos/?status=pendente` — list
- `GET /pedidos/count` — pending count
- `POST /pedidos/log-edit` — request log text change
- `POST /pedidos/viagem-edit` — request viagem data change
- `POST /pedidos/{id}/approve` — approve (admin)
- `POST /pedidos/{id}/reject` — reject (admin)

### Users
- `GET /users/` — list (admin)
- `POST /users/` — create (admin)
- `PUT /users/{id}` — update (admin)
- `DELETE /users/{id}` — delete (admin)

### Config
- `GET /config/` — get tenant config
- `PUT /config/` — update alert settings (admin)
- `PUT /config/fronteira-contacts` — update frontier contacts (admin)

### Tenants (master key)
- `GET /tenants/` — list all tenants
- `POST /tenants/` — create tenant (auto-creates admin + operador users)

---

## Deploy to Railway

### 1. Create GitHub repo

```bash
mkdir control-backend && cd control-backend
git init
# copy all files here
git add .
git commit -m "Control backend v1"
git remote add origin https://github.com/YOUR_USER/control-backend.git
git push -u origin main
```

### 2. Railway setup

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Select your `control-backend` repo
3. Click **+ New** → **Database** → **PostgreSQL**
4. Railway auto-injects `DATABASE_URL`

### 3. Add environment variables

In Railway → your service → **Variables**, add:

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MASTER_API_KEY` | A strong key for tenant creation |
| `CORS_ORIGINS` | `*` for now, lock down later |
| `MEDIA_DIR` | `/app/media` |

### 4. Add a volume for photos

In Railway → your service → **Settings** → **Volumes** → **Mount Volume**
- Mount path: `/app/media`

### 5. Generate domain

Railway → service → **Settings** → **Domains** → **Generate Domain**
→ You get something like `control-api-production.up.railway.app`

### 6. Create your first tenant

```bash
curl -X POST https://YOUR-DOMAIN.up.railway.app/tenants/ \
  -H "Content-Type: application/json" \
  -H "x-master-key: YOUR_MASTER_KEY" \
  -d '{"name":"Alltrans Angola","slug":"alltrans","admin_username":"admin","admin_password":"CHANGE_ME"}'
```

### 7. Test login

```bash
curl -X POST https://YOUR-DOMAIN.up.railway.app/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"CHANGE_ME"}'
```

You should get back a JWT token. Backend is live.

---

## Local development

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# Uses SQLite by default (control_dev.db)
# Swagger docs at http://localhost:8000/docs
```

---

## Migration path

Railway → own server is just:
1. `pg_dump` the Railway database
2. Copy media files
3. `pg_restore` on your server
4. Point DNS to your server
