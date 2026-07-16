# Deployment Guide

This guide provides instructions on how to build, run, and deploy the AI-First HCP CRM - Log Interaction Module.

---

## 🐋 Setup & Deployment via Docker Compose (Recommended)

Docker Compose is the easiest way to spin up the entire application locally or on a server. It packages the frontend, backend, and MySQL database, configuring networking automatically.

### Prerequisites
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
* A Groq API Key (get one from [Groq Console](https://console.groq.com/)).

### Steps to Run

1. **Verify your Root `.env` file**
   Ensure the root directory contains a `.env` file with your Groq API Key:
   ```env
   GROQ_API_KEY=gsk_...
   ```
   *(Note: The `docker-compose.yml` is configured to pass this API key from the host process or `.env` file automatically).*

2. **Launch all services**
   Run the following command in the root folder:
   ```bash
   docker-compose up --build
   ```
   This will pull/build and spin up:
   * **MySQL Database Container** on port `3306` (with healthcheck status polling).
   * **FastAPI Backend Container** on port `8000`.
   * **React Frontend Container** served on port `80` using Nginx.

3. **Seed Mock Healthcare Professionals (HCPs)**
   Once all containers are running, run the following command to populate the database with test doctors:
   ```bash
   docker-compose exec backend python seed.py
   ```
   You should see:
   `Successfully seeded 5 Healthcare Professionals (HCPs) into the database.`

4. **Access the Application**
   Open your browser and navigate to:
   * **Frontend UI**: [http://localhost](http://localhost)
   * **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
   * **Backend Health Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🛠️ Manual Local Deployment

If you prefer to run the application components individually without Docker, follow these steps:

### Backend Setup
1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```
2. **Setup virtual environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure environment variables**:
   Create a `.env` file inside `backend/` (or in the root folder):
   ```env
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=yourpassword
   DB_NAME=hcp_crm
   GROQ_API_KEY=gsk_...
   ```
5. **Database Setup**:
   Ensure you have a running MySQL instance with the database name matched to `DB_NAME`. SQLAlchemy will automatically create tables on startup.
6. **Seed Database**:
   ```bash
   python seed.py
   ```
7. **Start FastAPI server**:
   ```bash
   python run.py
   ```

### Frontend Setup
1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```
2. **Install dependencies**:
   ```bash
   npm install
   ```
3. **Start development server**:
   ```bash
   npm run dev
   ```
   The application will be accessible at [http://localhost:5173](http://localhost:5173).

---

## ☁️ Cloud Deployment Strategies

To host this application in a production/cloud environment, here are recommended strategies:

### 1. Frontend Hosting (Vite React App)
Because the built React app is fully static, you can deploy it to any static hosting provider.
* **Vercel / Netlify / Cloudflare Pages**:
  * Connect your GitHub repo.
  * Set **Build Command**: `npm run build`
  * Set **Output Directory**: `dist`
  * Add the following environment variable to the build configuration:
    * `VITE_API_BASE_URL`: The URL of your deployed Backend API (e.g. `https://api.yourdomain.com`).

### 2. Backend API Hosting (FastAPI)
The backend requires a persistent environment to run.
* **Render / Fly.io / Railway**:
  * Create a new Web Service pointing to your backend repo folder.
  * Set build command to: `pip install -r requirements.txt`
  * Set start command to: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  * Set the environment variables in the service dashboard:
    * `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (pointing to your cloud database).
    * `GROQ_API_KEY` (your API key).
    * `CORS_ORIGINS` (comma-separated list of allowed frontend domains, e.g., `https://your-frontend.vercel.app`).
* **AWS App Runner / ECS**:
  * You can build your backend container using the provided `backend/Dockerfile` and push it to AWS ECR.
  * Launch it on AWS App Runner or ECS Fargate, passing environment variables securely.

### 3. Database Hosting (MySQL)
* **Managed SQL Databases** (e.g., Aiven, DigitalOcean Managed DB, AWS RDS MySQL):
  * Create a managed MySQL database instance.
  * Obtain the connection credentials (host, port, user, password).
  * Run the backend with these credentials, and SQLAlchemy will initialize the schema.
