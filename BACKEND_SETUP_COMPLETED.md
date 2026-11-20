# SmartStock AI Backend - Complete Setup Guide

## Quick Start Checklist

### 1. Prerequisites
- [x] Python 3.10+ installed
- [x] PostgreSQL installed and running
- [x] Virtual environment created
- [ ] Dependencies installed (in progress...)
- [ ] Database created in PostgreSQL

### 2. Django Setup Steps
```bash
# Step 1: Run migrations
python manage.py makemigrations inventory
python manage.py migrate

# Step 2: Create superuser
python manage.py createsuperuser

# Step 3: Collect static files
python manage.py collectstatic --noinput

# Step 4: Load sample data (optional)
python manage.py seed_data

# Step 5: Start server
python manage.py runserver
```

### 3. Database Setup
The database will be created automatically when you run migrations.
PostgreSQL configuration from `.env`:
- Database: `smartstock`
- User: `postgres`
- Password: `password` (change in production)
- Host: `localhost`
- Port: `5432`

### 4. Key Endpoints After Setup
- Admin: http://127.0.0.1:8000/admin/
- Dashboard: http://127.0.0.1:8000/dashboard/
- POS: http://127.0.0.1:8000/pos/
- Chatbot: http://127.0.0.1:8000/ai-features/chatbot/
- Forecasting: http://127.0.0.1:8000/ai-features/forecast-dashboard/
- Semantic Search: http://127.0.0.1:8000/ai-features/semantic-search/

### 5. User Roles
- **Admin**: Full access to system
- **Manager**: Access to reports and analytics
- **Cashier**: POS and transaction entry

### 6. AI Features Setup
- **Ollama Chatbot**: Install Ollama and run `ollama serve` (runs on port 11434)
- **Demand Forecasting**: Run `python manage.py run_forecasts` (requires 30+ days of sales data)
- **Semantic Search**: Automatically indexed when products are created

### 7. Next Steps After Django Setup
1. Access admin dashboard
2. Add categories and suppliers
3. Create products
4. Test POS system
5. Run demand forecasts
6. Configure Ollama for chatbot

## Important Notes
- The `CustomUser` model replaces Django's default User model
- All users must have a role assigned (Admin, Manager, or Cashier)
- Stock movements are automatically tracked for audit purposes
- Chat history is preserved in the database
- Forecast results are stored separately for reporting

## Troubleshooting
- If migrations fail, check PostgreSQL is running: `psql -U postgres`
- If Ollama fails to connect, ensure it's running on http://localhost:11434
- Clear Django cache if templates don't update: `python manage.py clear_cache`
