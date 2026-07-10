# HCP Interaction Module — Frontend

A single-page, AI-first CRM screen for logging Healthcare Professional (HCP)
interactions. This is the **frontend only** — no backend, FastAPI, LangGraph,
or AI logic is implemented here. The UI is wired up so it can be connected to
a FastAPI backend later via Axios.

## Tech Stack

- React 19 + Vite
- Redux Toolkit (single slice, no thunks/middleware)
- Tailwind CSS
- Axios (placeholder API calls only)

## Project Structure

```
frontend/
  src/
    components/
      Header.jsx          — top bar with app title
      InteractionForm.jsx  — left panel, the full interaction form
      FormField.jsx        — reusable label + input component
      AIChat.jsx           — right panel, AI assistant chat UI
    redux/
      store.js             — Redux store setup
      interactionSlice.js  — the single slice holding all form + chat state
    services/
      api.js               — Axios instance + placeholder endpoints
    App.jsx
    main.jsx
    index.css
```

## Getting Started

```bash
npm install
npm run dev
```

The app runs at `http://localhost:5173`.

To build for production:

```bash
npm run build
```

## Notes

- `services/api.js` points at `http://localhost:8000` and exposes
  `logInteraction()`, `sendChat()`, and `getInteraction()` as placeholders.
  These calls will fail until a real backend exists — that's expected.
- The AI Assistant panel is UI only. No responses are generated; sending a
  message just adds it to the conversation and fires the (currently
  no-op) `sendChat()` placeholder.
- `aiSuggestions` starts empty and is only ever populated by a future
  backend/LLM — nothing is hardcoded.
