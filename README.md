# DailyBlog AI – Intelligent Automated Blog Generation

DailyBlog AI is an enterprise-grade, AI-powered automated blog generation and publishing system built for B2B companies. It streamlines the entire content lifecycle—from AI-driven topic ideation and SEO-optimized drafting to editorial governance and automated WordPress publishing.

## Key Features
- **Role-Based Workflows**: Strictly segmented workspaces for Company Admins, Editors, and Reviewers.
- **RAG & Memory Augmented Ideation**: Topics are suggested based on company context and historical knowledge.
- **Automated Synthesis**: Generates SEO-ready drafts adhering to strict brand voice and formatting rules.
- **Governance & Approval Pipeline**: Ensures content is reviewed before scheduling.
- **Automated Publishing**: Background workers seamlessly push approved content to WordPress.

## Tech Stack
- **Frontend**: React (Vite), TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python), SQLAlchemy, APScheduler
- **Database**: PostgreSQL (pgvector supported)
- **AI**: Google Gemini (via external LLM compatibility layer)

---

## Setup & Installation Instructions

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- PostgreSQL (v14+)
- Google AI Studio API Key (Gemini)

### 1. Database Setup
Ensure PostgreSQL is running. Create a database named `dailyblog`.
```sql
CREATE DATABASE dailyblog;
CREATE USER dailyblog_user WITH ENCRYPTED PASSWORD 'dailyblog_password';
GRANT ALL PRIVILEGES ON DATABASE dailyblog TO dailyblog_user;
```

### 2. Backend Setup
Navigate to the root directory and install Python dependencies:
```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
cd backend
pip install -r requirements.txt
```

Set up your `.env` file in the root directory (copy from a `.env.example` if available) and insert your LLM API Key:
```env
DATABASE_URL=postgresql+psycopg://dailyblog_user:dailyblog_password@localhost:5432/dailyblog
LLM_PROVIDER=external
LLM_API_KEY=your_google_ai_studio_api_key
LLM_MODEL=gemini-3.6-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

Run database migrations:
```bash
alembic upgrade head
```

Start the FastAPI backend server:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
Open a new terminal and navigate to the frontend directory:
```bash
cd frontend
npm install
npm run dev
```

### 4. Access the Application
- Open your browser to `http://localhost:5173`
- Default seeded test accounts (if you ran the seed script):
  - **Admin**: `admin@test.com` (password: `password123`)
  - **Editor**: `editor@test.com` (password: `password123`)
  - **Reviewer**: `reviewer@test.com` (password: `password123`)

---

## Documentation
Please refer to [SUBMISSION.md](./SUBMISSION.md) for the complete Product Requirements Document (PRD), Architecture Diagrams, ER Models, AI Prompt Strategy, and Test Scenarios. 
Sample AI generation output can be found in [SAMPLE_OUTPUT.md](./SAMPLE_OUTPUT.md).
