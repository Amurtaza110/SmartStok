# SmartStock — Inventory and AI Services
## Setup Guide

## Recommended: Docker Compose

1. Copy `.env.example` to `.env`.
2. Set unique random values for `SECRET_KEY`, `DB_PASSWORD`, `AI_SERVICE_TOKEN`, and `INVENTORY_SERVICE_TOKEN`.
3. Run `docker compose up --build`.
4. Create an administrator with `docker compose exec inventory python manage.py createsuperuser`.

Open the application at http://localhost:8000. Compose starts the Django inventory service, the independent AI service, and PostgreSQL. For service boundaries and API contracts, see [MICROSERVICES.md](./MICROSERVICES.md).

Existing SQLite data is preserved; Compose creates a separate PostgreSQL data volume. Export and migrate existing records separately before moving an existing installation.

---

## 🗂️ PROJECT STRUCTURE

```
smartstock/
├── manage.py
├── requirements.txt
├── .env.example
├── logs/
│
├── smartstock/              # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── inventory/               # Core inventory app
│   ├── models.py            # Database models
│   ├── views.py             # Class-Based Views (CBVs)
│   ├── urls.py              # URL routing
│   ├── forms.py             # Django forms
│   ├── admin.py             # Django Admin customization
│   └── internal_api.py      # Token-protected AI data endpoints
│
├── ai_assistant/            # AI features app
│   ├── views.py             # Chatbot, Forecast, Search views
│   ├── urls.py
│   └── services/
│       └── ai_service_client.py # HTTP client for the independent AI service
├── ai_service/              # Independent FastAPI service
│   └── app.py               # Chat, semantic search, forecasting APIs
│
├── templates/
│   ├── base.html            # Master layout with sidebar
│   ├── registration/
│   │   └── login.html
│   ├── inventory/
│   │   ├── dashboard.html
│   │   ├── product_list.html
│   │   ├── product_detail.html  # Includes forecast chart
│   │   ├── product_form.html
│   │   ├── pos.html             # Point of Sale
│   │   ├── sale_list.html
│   │   └── stock_adjustment.html
│   └── ai_assistant/
│       ├── chatbot.html         # AI Chat interface
│       ├── semantic_search.html # Smart Search
│       └── forecast_dashboard.html
│
└── static/
    ├── css/
    └── js/
Dockerfile                   # Django inventory service image
docker-compose.yml           # Local multi-service deployment
```

---

## ⚙️ STEP 1 — PREREQUISITES

### Python (3.10+)
```bash
python --version   # Must be 3.10+
```

### PostgreSQL
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# Windows: Download from https://www.postgresql.org/download/windows/
```

### Create Database
```sql
-- Run in psql
CREATE DATABASE smartstock;
CREATE USER smartstock_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE smartstock TO smartstock_user;
```

---

## ⚙️ STEP 2 — PYTHON SETUP

```bash
# Clone / extract project
cd smartstock

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Linux/Mac
# venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r ai_service/requirements.txt
```

### Create .env file
```bash
cp .env.example .env
# Set database credentials, secret key, and both service tokens
```

---

## ⚙️ STEP 3 — DJANGO SETUP

```bash
# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Start Django (AI service must run separately)
python manage.py runserver
```

In a second terminal, start the AI service:

```powershell
uvicorn ai_service.app:app --host 127.0.0.1 --port 8001
```

After importing an existing database, run `python manage.py migrate_ai_data` while the AI service is online to copy legacy chat and forecast data into its own database.

Open: http://127.0.0.1:8000
Admin: http://127.0.0.1:8000/admin

---

## 🌐 PUBLIC DEPLOYMENT ON VERCEL

Vercel detects this Django project from `manage.py`, installs the root
`requirements.txt`, and collects static files during the build. Do not set a
custom output directory or build command.

1. Import the GitHub repository into Vercel and select the repository root.
2. Create a persistent PostgreSQL database with a provider such as Neon or
   Supabase. Add its PostgreSQL connection string as the sensitive
   `DATABASE_URL` environment variable in Vercel for both Preview and Production.
3. Add a unique `SECRET_KEY` and set `DEBUG=False`. Vercel deployment hostnames
   are added automatically. For a custom domain, also set `ALLOWED_HOSTS` to its
   hostname and `CSRF_TRUSTED_ORIGINS` to its HTTPS origin, for example
   `https://stock.example.com`.
4. Deploy. Set the same Vercel environment variables as the target environment,
   then run database migrations once for that database:

   ```bash
   vercel env run -- python manage.py migrate --noinput
   ```

   This requires the repository to be linked locally with the Vercel CLI and
   the CLI to be authenticated. Do not run migrations as part of the build.
5. Create the first administrator against the same database:

   ```bash
   vercel env run -- python manage.py createsuperuser
   ```

The inventory application can run without the AI service. Chat, semantic search,
and AI forecasts require deploying `ai_service` separately with a reachable
Ollama instance, then setting `AI_SERVICE_URL`, `AI_SERVICE_TOKEN`, and
`INVENTORY_SERVICE_TOKEN` in both services. The AI service's bundled SQLite
database is not persistent hosting storage.

---

## 🤖 STEP 4 — OLLAMA AI CHATBOT SETUP

### Install Ollama
```bash
# Linux / WSL2
curl -fsSL https://ollama.com/install.sh | sh

# Mac
brew install ollama

# Windows: Download from https://ollama.com/download
```

### Download AI Model (choose one)
```bash
# Option A: Llama 3.2 (Recommended, ~2GB)
ollama pull llama3.2

# Option B: Gemma 3 (Google, ~2GB)
ollama pull gemma3

# Option C: Mistral (faster, ~4GB)
ollama pull mistral
```

### Start Ollama Server
```bash
ollama serve
# Runs on http://localhost:11434
```

### Verify
```bash
curl http://localhost:11434/api/tags
# Should list downloaded models
```

### Configure in .env
```bash
OLLAMA_MODEL=llama3.2   # Match the model you pulled
```

---

## 🔍 STEP 5 — SEMANTIC SEARCH SETUP

```bash
# The sentence-transformers library is in ai_service/requirements.txt
# Model downloads automatically on first use (all-MiniLM-L6-v2, ~22MB)

# The AI service reads the current product catalog over the protected inventory API.
# Use the web UI's re-index action to warm its in-process search index.
```

---

## 📈 STEP 6 — DEMAND FORECASTING SETUP

```bash
# Run forecasts for active products with recorded sales
python manage.py run_forecasts

# Run for single product
python manage.py run_forecasts --product 1

# Run forecasts and reindex embeddings together
python manage.py run_forecasts --reindex

# Schedule daily via cron (Linux)
# Add to crontab -e:
# 0 2 * * * /path/to/venv/bin/python /path/to/manage.py run_forecasts
```

---

## 🗄️ COMPLETE SQL REFERENCE (For Viva)

### A. DDL — Data Definition Language

```sql
-- ═══ CREATE ═══════════════════════════════════════════

-- Create database
CREATE DATABASE smartstock;

-- Categories table
CREATE TABLE inventory_category (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    icon        VARCHAR(50) DEFAULT 'bi-box-seam'
);

-- Suppliers table
CREATE TABLE inventory_supplier (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(200) NOT NULL,
    contact    VARCHAR(50),
    address    TEXT,
    email      VARCHAR(100),
    city       VARCHAR(100),
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table (core entity)
CREATE TABLE inventory_product (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(200) NOT NULL,
    generic_name     VARCHAR(200),
    description      TEXT,
    tags             VARCHAR(300),
    barcode          VARCHAR(100) UNIQUE NOT NULL,
    category_id      INTEGER REFERENCES inventory_category(id) ON DELETE SET NULL,
    supplier_id      INTEGER REFERENCES inventory_supplier(id) ON DELETE SET NULL,
    purchase_price   DECIMAL(10,2) NOT NULL CHECK (purchase_price >= 0),
    selling_price    DECIMAL(10,2) NOT NULL CHECK (selling_price >= 0),
    unit             VARCHAR(50) DEFAULT 'pcs',
    min_stock        INTEGER DEFAULT 10,
    reorder_point    INTEGER DEFAULT 20,
    current_stock    INTEGER DEFAULT 0,
    expiry_date      DATE,
    batch_number     VARCHAR(100),
    embedding_json   TEXT,         -- AI: sentence-transformer vector
    last_reorder_qty INTEGER DEFAULT 0,  -- AI: forecasted reorder qty
    image            VARCHAR(200),
    is_active        BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users with roles
CREATE TABLE inventory_customuser (
    id           SERIAL PRIMARY KEY,
    username     VARCHAR(150) UNIQUE NOT NULL,
    email        VARCHAR(254),
    password     VARCHAR(128) NOT NULL,
    role         VARCHAR(20) DEFAULT 'Cashier',
    phone        VARCHAR(20),
    is_active    BOOLEAN DEFAULT TRUE,
    is_staff     BOOLEAN DEFAULT FALSE,
    is_superuser BOOLEAN DEFAULT FALSE,
    date_joined  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sales (invoice header)
CREATE TABLE inventory_sale (
    id              SERIAL PRIMARY KEY,
    invoice_number  VARCHAR(50) UNIQUE NOT NULL,
    customer_name   VARCHAR(200) DEFAULT 'Walk-in Customer',
    customer_phone  VARCHAR(20),
    total_amount    DECIMAL(12,2) DEFAULT 0,
    discount        DECIMAL(10,2) DEFAULT 0,
    paid_amount     DECIMAL(12,2) DEFAULT 0,
    status          VARCHAR(10) DEFAULT 'completed',
    cashier_id      INTEGER REFERENCES inventory_customuser(id) ON DELETE SET NULL,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sale items (invoice detail)
CREATE TABLE inventory_saleitem (
    id          SERIAL PRIMARY KEY,
    sale_id     INTEGER NOT NULL REFERENCES inventory_sale(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES inventory_product(id) ON DELETE CASCADE,
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(12,2) NOT NULL
);

-- Stock movements (audit trail)
CREATE TABLE inventory_stockmovement (
    id            SERIAL PRIMARY KEY,
    product_id    INTEGER NOT NULL REFERENCES inventory_product(id) ON DELETE CASCADE,
    movement_type VARCHAR(10) NOT NULL,   -- IN, OUT, ADJUST, RETURN, EXPIRED
    quantity      INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    unit_price    DECIMAL(10,2) DEFAULT 0,
    notes         TEXT,
    reference     VARCHAR(100),
    created_by_id INTEGER REFERENCES inventory_customuser(id) ON DELETE SET NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI: Chat history
CREATE TABLE inventory_chathistory (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES inventory_customuser(id) ON DELETE CASCADE,
    session_id VARCHAR(100) NOT NULL,
    role       VARCHAR(10) NOT NULL,    -- user | assistant
    message    TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI: Demand forecast results
CREATE TABLE inventory_forecastresult (
    id                    SERIAL PRIMARY KEY,
    product_id            INTEGER UNIQUE REFERENCES inventory_product(id) ON DELETE CASCADE,
    forecast_dates_json   TEXT NOT NULL,
    forecast_values_json  TEXT NOT NULL,
    recommended_reorder   INTEGER DEFAULT 0,
    model_used            VARCHAR(100) DEFAULT 'RandomForest',
    mae                   FLOAT DEFAULT 0,
    generated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ═══ ALTER ════════════════════════════════════════════

-- Add a new column
ALTER TABLE inventory_product ADD COLUMN discount_percent DECIMAL(5,2) DEFAULT 0;

-- Change default value
ALTER TABLE inventory_product ALTER COLUMN min_stock SET DEFAULT 20;

-- Rename a column
ALTER TABLE inventory_product RENAME COLUMN unit TO measurement_unit;
-- (rename back for Django compatibility)
ALTER TABLE inventory_product RENAME COLUMN measurement_unit TO unit;

-- Add constraint
ALTER TABLE inventory_product ADD CONSTRAINT chk_stock_positive
    CHECK (current_stock >= 0);

-- Add index for performance
CREATE INDEX idx_product_category ON inventory_product(category_id);
CREATE INDEX idx_sale_created_at  ON inventory_sale(created_at);
CREATE INDEX idx_movement_product ON inventory_stockmovement(product_id);

-- Add foreign key
ALTER TABLE inventory_saleitem
    ADD CONSTRAINT fk_sale FOREIGN KEY (sale_id) REFERENCES inventory_sale(id);


-- ═══ DROP ════════════════════════════════════════════

-- Drop column (careful!)
ALTER TABLE inventory_product DROP COLUMN IF EXISTS discount_percent;

-- Drop index
DROP INDEX IF EXISTS idx_product_category;

-- Drop table (with cascade)
DROP TABLE IF EXISTS inventory_chathistory CASCADE;

-- Drop constraint
ALTER TABLE inventory_product DROP CONSTRAINT IF EXISTS chk_stock_positive;

-- Truncate (clear all data, keep structure)
TRUNCATE TABLE inventory_saleitem CASCADE;
TRUNCATE TABLE inventory_sale CASCADE;
```

---

### B. DML — Data Manipulation Language

```sql
-- ═══ INSERT ══════════════════════════════════════════

INSERT INTO inventory_category (name, description)
VALUES
    ('Medicine',  'Pharmaceutical products'),
    ('Cosmetics', 'Beauty and personal care'),
    ('Vitamins',  'Nutritional supplements'),
    ('Snacks',    'Food and beverages');

INSERT INTO inventory_supplier (name, contact, city, email)
VALUES
    ('MediPlus Pharma',   '0300-1234567', 'Karachi',   'info@mediplus.pk'),
    ('HealthFirst Dist.', '0321-9876543', 'Lahore',    'info@healthfirst.pk');

INSERT INTO inventory_product
    (name, generic_name, barcode, category_id, supplier_id,
     purchase_price, selling_price, current_stock, min_stock,
     expiry_date, batch_number, tags)
VALUES
    ('Paracetamol 500mg', 'Acetaminophen', 'PKT-001', 1, 1,
     5.50, 12.00, 450, 20, '2026-12-31', 'BATCH001', 'fever,pain,headache'),

    ('Ibuprofen 400mg', 'Ibuprofen', 'PKT-002', 1, 1,
     8.00, 18.00, 200, 20, '2026-08-15', 'BATCH002', 'pain,inflammation'),

    ('Vitamin C 1000mg', 'Ascorbic Acid', 'PKT-006', 3, 2,
     18.00, 45.00, 300, 30, '2027-06-30', 'BATCH006', 'vitamin,immunity');


-- ═══ UPDATE ══════════════════════════════════════════

-- Reduce stock after sale
UPDATE inventory_product
SET current_stock = current_stock - 10,
    updated_at    = CURRENT_TIMESTAMP
WHERE barcode = 'PKT-001';

-- Price change
UPDATE inventory_product
SET selling_price = 15.00
WHERE name LIKE '%Paracetamol%';

-- Reactivate product
UPDATE inventory_product
SET is_active = TRUE
WHERE id = 5;

-- Bulk price increase by 10%
UPDATE inventory_product
SET selling_price = ROUND(selling_price * 1.10, 2)
WHERE category_id = (SELECT id FROM inventory_category WHERE name = 'Medicine');


-- ═══ DELETE ══════════════════════════════════════════

-- Soft delete (recommended — preserves audit trail)
UPDATE inventory_product SET is_active = FALSE WHERE id = 10;

-- Hard delete out-of-stock products (use carefully)
DELETE FROM inventory_product WHERE current_stock = 0 AND is_active = FALSE;

-- Delete inactive supplier
DELETE FROM inventory_supplier WHERE is_active = FALSE AND id = 5;

-- Clear old chat history (>30 days)
DELETE FROM inventory_chathistory
WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
```

---

### C. DQL — Data Query Language (Reports)

```sql
-- ═══ SELECT QUERIES ═══════════════════════════════════

-- 1. Low stock products (for dashboard alert)
SELECT p.name, p.generic_name, p.current_stock, p.min_stock,
       s.name AS supplier, c.name AS category
FROM inventory_product p
LEFT JOIN inventory_category c ON p.category_id = c.id
LEFT JOIN inventory_supplier  s ON p.supplier_id = s.id
WHERE p.current_stock <= p.min_stock AND p.is_active = TRUE
ORDER BY p.current_stock ASC;


-- 2. Expiring within 30 days
SELECT name, expiry_date, current_stock,
       (expiry_date - CURRENT_DATE) AS days_left
FROM inventory_product
WHERE expiry_date IS NOT NULL
  AND expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
  AND is_active = TRUE
ORDER BY expiry_date ASC;


-- 3. Monthly sales report
SELECT
    DATE_TRUNC('month', s.created_at) AS month,
    COUNT(DISTINCT s.id)              AS total_transactions,
    SUM(s.total_amount)               AS total_revenue,
    AVG(s.total_amount)               AS avg_sale_value
FROM inventory_sale s
WHERE s.status = 'completed'
  AND s.created_at >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', s.created_at)
ORDER BY month DESC;


-- 4. Top 10 best-selling products
SELECT
    p.name,
    p.category_id,
    SUM(si.quantity)               AS total_qty_sold,
    SUM(si.total_price)            AS total_revenue,
    COUNT(DISTINCT si.sale_id)     AS num_transactions
FROM inventory_saleitem si
JOIN inventory_product p ON si.product_id = p.id
JOIN inventory_sale s    ON si.sale_id = s.id
WHERE s.status = 'completed'
  AND s.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY p.id, p.name, p.category_id
ORDER BY total_qty_sold DESC
LIMIT 10;


-- 5. Total inventory value by category
SELECT
    c.name         AS category,
    COUNT(p.id)    AS product_count,
    SUM(p.current_stock * p.purchase_price) AS inventory_value,
    SUM(p.current_stock * p.selling_price)  AS retail_value
FROM inventory_category c
LEFT JOIN inventory_product p ON p.category_id = c.id AND p.is_active = TRUE
GROUP BY c.id, c.name
ORDER BY inventory_value DESC;


-- 6. Daily sales trend (last 7 days)
SELECT
    DATE(s.created_at) AS sale_date,
    COUNT(DISTINCT s.id) AS num_sales,
    SUM(s.total_amount)  AS revenue
FROM inventory_sale s
WHERE s.status = 'completed'
  AND s.created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(s.created_at)
ORDER BY sale_date;


-- 7. Products never sold
SELECT p.name, p.current_stock, p.created_at
FROM inventory_product p
WHERE p.id NOT IN (SELECT DISTINCT product_id FROM inventory_saleitem)
  AND p.is_active = TRUE;


-- 8. Profit analysis per product
SELECT
    p.name,
    p.purchase_price,
    p.selling_price,
    ROUND((p.selling_price - p.purchase_price), 2) AS profit_per_unit,
    ROUND(((p.selling_price - p.purchase_price) / p.selling_price * 100), 1) AS margin_pct,
    COALESCE(SUM(si.quantity), 0) AS units_sold,
    COALESCE(SUM(si.quantity) * (p.selling_price - p.purchase_price), 0) AS total_profit
FROM inventory_product p
LEFT JOIN inventory_saleitem si ON si.product_id = p.id
LEFT JOIN inventory_sale s ON si.sale_id = s.id AND s.status = 'completed'
WHERE p.is_active = TRUE
GROUP BY p.id, p.name, p.purchase_price, p.selling_price
ORDER BY total_profit DESC;


-- 9. Stock movement audit trail for one product
SELECT
    m.movement_type,
    m.quantity,
    m.balance_after,
    m.notes,
    m.reference,
    u.username AS performed_by,
    m.created_at
FROM inventory_stockmovement m
JOIN inventory_product p     ON m.product_id = p.id
LEFT JOIN inventory_customuser u ON m.created_by_id = u.id
WHERE p.name = 'Paracetamol 500mg'
ORDER BY m.created_at DESC;


-- 10. User activity report (cashier performance)
SELECT
    u.username,
    u.role,
    COUNT(s.id)     AS total_sales,
    SUM(s.total_amount) AS total_revenue,
    AVG(s.total_amount) AS avg_sale
FROM inventory_customuser u
LEFT JOIN inventory_sale s ON s.cashier_id = u.id AND s.status = 'completed'
WHERE s.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY u.id, u.username, u.role
ORDER BY total_revenue DESC;
```

---

### D. DCL — Data Control Language

```sql
-- Create application user
CREATE USER smartstock_app WITH PASSWORD 'securepassword';

-- Grant privileges
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smartstock_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smartstock_app;

-- Restrict sensitive table
REVOKE DELETE ON inventory_sale FROM smartstock_app;

-- Read-only user (for reports)
CREATE USER reports_user WITH PASSWORD 'readonly123';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reports_user;
```

---

### E. TCL — Transaction Control Language

```sql
-- Sale transaction (atomic — all or nothing)
BEGIN;
    -- Deduct stock
    UPDATE inventory_product
    SET current_stock = current_stock - 10
    WHERE id = 1 AND current_stock >= 10;

    -- Check it succeeded
    -- (In application code, check affected rows)

    -- Record movement
    INSERT INTO inventory_stockmovement
        (product_id, movement_type, quantity, balance_after, reference, created_by_id)
    VALUES (1, 'OUT', 10, 440, 'INV-20250101-001', 2);

    -- Create sale record
    INSERT INTO inventory_sale
        (invoice_number, customer_name, total_amount, paid_amount, status, cashier_id)
    VALUES ('INV-20250101-001', 'Ahmed Ali', 120.00, 150.00, 'completed', 2);

COMMIT;  -- Only commits if all steps succeeded

-- ROLLBACK if something fails
-- ROLLBACK;

-- Savepoint example
BEGIN;
    SAVEPOINT before_price_update;
    UPDATE inventory_product SET selling_price = 999 WHERE id = 1;
    -- Something went wrong...
    ROLLBACK TO SAVEPOINT before_price_update;
    -- Continue with other operations...
COMMIT;
```

---

## 🌐 URL MAP

| URL | View | Description |
|-----|------|-------------|
| `/` | DashboardView | Main dashboard |
| `/products/` | ProductListView | Product catalog |
| `/products/new/` | ProductCreateView | Add product |
| `/products/<id>/` | ProductDetailView | Product detail + forecast |
| `/products/<id>/stock/` | StockAdjustmentView | Adjust stock |
| `/pos/` | POSView | Point of sale terminal |
| `/pos/checkout/` | CheckoutView | Process sale (AJAX) |
| `/sales/` | SaleListView | Sales history |
| `/reports/` | ReportsView | Analytics & charts |
| `/ai/chat/` | ChatbotView | AI chatbot interface |
| `/ai/chat/api/` | ChatAPIView | Chat AJAX endpoint |
| `/ai/search/` | SemanticSearchView | Smart semantic search |
| `/ai-features/forecast/<id>/` | ForecastView | Product forecast (JSON) |
| `/ai-features/forecast/dashboard/` | ForecastDashboardView | All forecasts |
| `/ai-features/status/` | AIStatusView | AI component status |
| `/admin/` | Django Admin | Admin panel |

---

## 🏗️ DJANGO MVT ARCHITECTURE

```
Browser Request
      │
      ▼
  urls.py  ←─────────── URL Dispatcher
      │
      ▼
  views.py ←─────────── Controller Logic (CBVs)
      │         │
      │         ▼
      │    models.py ←── ORM → PostgreSQL
      │
      ▼
 templates/  ←────────── HTML + Chart.js rendering
      │
      ▼
Browser Response
```

**Class-Based Views used:**
- `TemplateView` → Dashboard, Reports
- `ListView` → Products, Sales, Categories, Suppliers
- `DetailView` → Product detail, Sale detail
- `CreateView` → Add product, category, supplier
- `UpdateView` → Edit product, category, supplier
- `DeleteView` → Delete/deactivate product
- `View` → POS, Stock adjustment, AI endpoints (custom logic)

---

## 🤖 AI ARCHITECTURE

```
User Query
    │
    ▼
SmartStock AI Chat (Django View)
    │
    ├── Build Context (RAG Pattern)
    │       ├── Query PostgreSQL for live inventory data
    │       ├── Low stock, expiry, sales summary
    │       └── Format as structured text
    │
    ├── Send to Ollama API (localhost:11434)
    │       ├── System prompt + live context
    │       ├── Conversation history (last 10 turns)
    │       └── User message
    │
    ▼
Ollama → Llama 3.2 / Gemma 3 (local LLM)
    │
    ▼
Response → Save to ChatHistory → Return to browser
```

---

## 📦 ROLE-BASED ACCESS CONTROL

| Feature | Admin | Manager | Cashier |
|---------|-------|---------|---------|
| Dashboard | ✅ | ✅ | ✅ |
| View Products | ✅ | ✅ | ✅ |
| Add/Edit Products | ✅ | ✅ | ❌ |
| Delete Products | ✅ | ❌ | ❌ |
| Adjust Stock | ✅ | ✅ | ❌ |
| Point of Sale | ✅ | ✅ | ✅ |
| View Sales | ✅ | ✅ | ✅ |
| Reports | ✅ | ✅ | ❌ |
| AI Chatbot | ✅ | ✅ | ✅ |
| AI Search | ✅ | ✅ | ✅ |
| Run Forecasts | ✅ | ✅ | ❌ |
| Re-index Embeddings | ✅ | ✅ | ❌ |
| Admin Panel | ✅ | ❌ | ❌ |

---

## 🛠️ COMMON ISSUES

**Q: Ollama is not running?**
```bash
# Check if running
curl http://localhost:11434/api/tags
# Start it
ollama serve
```

**Q: sentence-transformers slow on first use?**
> It downloads the model (~22MB) on first run. Subsequent runs are fast.

**Q: Not enough data for forecasting?**
> Forecasts require recorded, completed sales for that product. Enter real sales through the POS, then run `python manage.py run_forecasts`. No demo sales are generated.

**Q: Django migration errors?**
```bash
python manage.py makemigrations inventory
python manage.py migrate --run-syncdb
```
