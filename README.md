# 📦 SmartStock — AI-Powered Inventory Management System

SmartStock is a modern, full-featured, AI-powered inventory management web application built with **Django 5**, **Bootstrap 5**, and integrated AI capabilities (Demand Forecasting, Semantic Search, and Ollama-powered Chatbot with contextual fallback).

It runs as a **single, self-contained service** using **SQLite**, requiring **zero external database setup**, and is **100% compatible for deployment on Vercel** or local development.

---

## 🚀 Key Features

- **Dashboard & Analytics**: Real-time KPI metrics, stock valuation, monthly revenue, transaction charts, and quick actions.
- **Inventory Management**:
  - Products catalog with batch tracking, expiry date alerts, and reorder point warnings.
  - Category and Supplier management.
  - Stock movements and manual adjustments with full audit logs.
- **Point of Sale (POS)**:
  - Fast barcode and keyword search.
  - Dynamic invoice generation, receipt calculation, and automatic stock deduction.
- **AI Capabilities**:
  - 🤖 **AI Assistant (Chatbot)**: Context-aware assistant trained on real-time inventory facts (low stock, expiring items, revenue stats). Integrates with local Ollama (`llama3.2`) and gracefully falls back to instant database context when offline.
  - 📈 **Demand Forecasting**: Predicts next 30 days demand using a 14-day moving average and sales velocity to compute optimal reorder levels.
  - 🔍 **Smart Semantic Search**: Natural language search (e.g., *"fever medicine"* → Paracetamol) with automatic fallback to keyword lookup.
- **Role-Based Access Control**:
  - `Admin`: Full system access, administrator panel, user management.
  - `Manager`: Products, suppliers, inventory adjustments, reports, and forecasting.
  - `Cashier`: POS checkout, product search, sales lookup.

---

## 👥 Demo Accounts

The project includes a ready-to-use SQLite database populated with categories, products, sales history, and user accounts:

| Role | Username | Password | Access Level |
|------|----------|----------|--------------|
| **Admin** | `admin` | `admin123` | Full access (Admin panel + all features) |
| **Manager** | `manager` | `manager123` | Inventory, analytics, reports, forecasting |
| **Cashier** | `cashier` | `cashier123` | POS terminal, checkout, product search |

---

## ⚡ Quick Start (Local Development)

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 installed.

### 2. Setup & Run
```bash
# Clone the repository
git clone https://github.com/Amurtaza110/SmartStock.git
cd SmartStock

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations (pre-seeded db.sqlite3 is included)
python manage.py migrate

# Start the development server
python manage.py runserver
```

Open your browser at **http://127.0.0.1:8000/** and log in with any demo account!

---

## 🌐 Deploy to Vercel (1-Click Ready)

This repository is pre-configured for Vercel deployment:
- `vercel.json` routes all requests to `smartstock/wsgi.py`.
- `smartstock/settings.py` auto-detects Vercel, initializes writable SQLite in `/tmp/db.sqlite3` from the bundled seed database, configures `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` dynamically, and serves static files using WhiteNoise.

### Deployment Steps:
1. Push this repository to your GitHub account (or import `https://github.com/Amurtaza110/SmartStock.git`).
2. Go to [Vercel Dashboard](https://vercel.com/dashboard) and click **"Add New Project"**.
3. Import your GitHub repository.
4. Leave the **Build Command** and **Output Directory** default (handled automatically).
5. (Optional) In **Environment Variables**, you may set:
   - `SECRET_KEY`: Any secure random string (default is pre-configured).
6. Click **Deploy**.

Your SmartStock application will be live in seconds at `https://your-project.vercel.app`!

---

## 🤖 AI Features Configuration (Optional)

### Ollama (Local AI Chatbot)
The AI Assistant functions directly using real-time database context out of the box. To enable full generative LLM responses with Ollama:
1. Install Ollama: [https://ollama.com](https://ollama.com)
2. Pull the model:
   ```bash
   ollama pull llama3.2
   ```
3. Start Ollama:
   ```bash
   ollama serve
   ```
4. SmartStock will automatically connect to Ollama at `http://localhost:11434`.

---

## 📁 Project Architecture

```
SmartStock/
├── api/
│   └── index.py            # Vercel Serverless Function entrypoint
├── smartstock/
│   ├── settings.py         # Unified Django settings (SQLite, WhiteNoise, Vercel detection)
│   ├── urls.py             # Main URL routing
│   └── wsgi.py             # WSGI application callable
├── inventory/
│   ├── models.py           # CustomUser, Product, Category, Supplier, Sale, SaleItem, etc.
│   ├── views.py            # CBVs for Dashboard, Products, POS, Sales, Reports
│   ├── forms.py            # Form validation
│   ├── admin.py            # Django Admin registration
│   └── urls.py             # Inventory routing
├── ai_assistant/
│   ├── views.py            # Views for Chatbot, Forecasting, and Semantic Search
│   ├── urls.py             # AI feature routes
│   └── services/
│       ├── forecasting.py      # Demand forecasting & moving average calculations
│       ├── ollama_service.py   # Ollama integration & live inventory context builder
│       └── semantic_search.py  # Semantic vector search & keyword fallback
├── templates/              # Bootstrap 5 responsive templates
├── static/                 # CSS, JavaScript, and UI assets
├── staticfiles/            # Pre-collected production static files (WhiteNoise)
├── db.sqlite3              # Pre-seeded database with sample data & demo users
├── vercel.json             # Vercel deployment configuration
├── requirements.txt        # Production Python dependencies
└── manage.py               # Django management script
```

---

## 📄 License
This project is open-source and available under the MIT License.
