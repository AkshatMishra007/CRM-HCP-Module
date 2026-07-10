# AI-First HCP CRM - Log Interaction Module

An intelligent, AI-first Customer Relationship Management (CRM) log interaction screen designed specifically for medical representatives in the life sciences sector. This application integrates an advanced conversational interface with standard CRM data-logging pipelines, enabling medical representatives to quickly log detailed interactions, clinical trials, sample distributions, and follow-ups with Healthcare Professionals (HCPs) using natural language.

---

## 🚀 Key Features

* **AI Chat Assistant (Groq & LLaMA 3.3)**: Natural language chat interface that parses unstructured representative notes and extracts detailed structured interaction attributes.
* **LangGraph Pipeline Workflow**: Leverages a structured agent graph with distinct nodes for extraction, interaction summarization, and next-action suggestions.
* **Reactive Autocomplete HCP Search**: Debounced database query component that matches name, hospital, or specialization, automatically selecting the HCP when a unique match is returned.
* **Dynamic Location Fallback**: Prioritizes AI extracted locations, manually input values, and the doctor's primary hospital in a unified priority waterfall.
* **Nested Entity Sync (Delete-and-Reinsert)**: Atomically logs and updates nested child entities such as distributed samples, shared materials, and suggestions in single database transactions.
* **Automatic Quantity Parsing**: Intelligent text parser that extracts sample quantities and product names from statements like `"5 samples of CardioX 10 mg"`.
* **Redux Global State Management**: Centralized store tracking form data, toast notifications, active editing ID, chat histories, and selected HCP context.

---

## 🛠️ Architecture Overview

The system is split into a **React + Redux** single-page application and a **FastAPI + SQLAlchemy** backend connected to a **MySQL** database.

```mermaid
graph TD
    subgraph Frontend [React Single Page App]
        AIChat[AIChat Component]
        InteractionForm[InteractionForm Component]
        ReduxStore[(Redux Store)]
    end

    subgraph Backend [FastAPI Service]
        FastAPI[API Router]
        LangGraph[LangGraph Agent Engine]
        SQLAlchemy[SQLAlchemy ORM]
    end

    subgraph External [External Services & Database]
        Groq[Groq LLaMA 3.3 API]
        MySQL[(MySQL DB)]
    end

    AIChat -->|Send Chat Message| FastAPI
    InteractionForm -->|Get Doctors & Log Interactions| FastAPI
    
    FastAPI -->|Invoke StateGraph| LangGraph
    LangGraph -->|LLM Prompts & Responses| Groq
    
    FastAPI -->|Query/Commit Models| SQLAlchemy
    SQLAlchemy -->|PyMySQL Driver| MySQL
    
    ReduxStore <-->|Global State Sync| AIChat
    ReduxStore <-->|Selected HCP & Edit Context| InteractionForm
```

### LangGraph Workflow

The AI agent compiles into a linear state graph consisting of three nodes:

1. **Extract Node (`extract`)**: Uses `ChatGroq` LLaMA 3.3 to extract fields (name, location, materials, samples, sentiment, outcomes) into a strict JSON schema.
2. **Summary Node (`summary`)**: Generates a concise 2-3 sentence overview of the interaction.
3. **Suggestions Node (`suggestions`)**: Suggests 3 actionable, structured follow-up next steps.

```mermaid
graph LR
    START((START)) --> Extract[extract]
    Extract --> Summary[summary]
    Summary --> Suggestions[suggestions]
    Suggestions --> END((END))
```

---

## 📊 Database Models & Relationships

```mermaid
erDiagram
    HCP {
        int id PK
        string name
        string hospital
        string specialization
        string city
        datetime created_at
    }
    Interaction {
        int id PK
        int hcp_id FK
        string interaction_type
        date interaction_date
        time interaction_time
        string meeting_location
        string attendees
        string topics_discussed
        string ai_summary
        string sentiment
        string outcomes
        string follow_up_actions
        datetime created_at
    }
    Material {
        int id PK
        int interaction_id FK
        string material_name
    }
    Sample {
        int id PK
        int interaction_id FK
        string sample_name
        int quantity
    }
    AISuggestion {
        int id PK
        int interaction_id FK
        string suggestion
    }

    HCP ||--o{ Interaction : logs
    Interaction ||--o{ Material : includes
    Interaction ||--o{ Sample : distributes
    Interaction ||--o{ AISuggestion : proposes
```

---

## ⚡ API Endpoints

### 🩺 Healthcare Professionals (HCPs)
* `GET /hcps/` - Lists all registered doctors.
* `GET /hcps/search?q={query}` - Autocomplete search by name, hospital, or specialty.
* `POST /hcps/` - Creates a new doctor record.
* `PUT /hcps/{id}` - Updates a doctor's profile.

### 📝 Interactions
* `POST /interactions/` - Logs a new representative-HCP interaction, parsing samples and evaluating location fallback.
* `PUT /interactions/{id}` - Updates an existing log, executing transactional delete-and-reinsert list synchronization.
* `GET /interactions/{id}` - Retrieves a specific interaction log by ID.
* `GET /interactions/history/{hcp_id}` - Retrieves historical interaction logs for a given physician ordered by date and ID descending.

### 🤖 AI Agent Chat
* `POST /chat/` - Takes raw conversation/notes, invokes the LangGraph pipeline, and returns extracted JSON data, summary, and action suggestions.

---

## ⚙️ Setup & Installation

### Backend Setup

1. **Navigate to backend and configure environment**:
   Create a `.env` file inside the `backend/` directory:
   ```env
   DATABASE_URL=mysql+pymysql://<user>:<password>@localhost:3306/hcp_crm
   GROQ_API_KEY=gsk_...
   ```

2. **Activate the Virtual Environment**:
   ```powershell
   # Windows PowerShell
   .venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the FastAPI App**:
   ```bash
   python run.py
   ```
   The backend will be available at `http://127.0.0.1:8000`.

---

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install Dependencies**:
   ```bash
   npm install
   ```

3. **Start Development Server**:
   ```bash
   npm run dev
   ```
   The Vite app will open at `http://localhost:5173`.
