# Autonomous AI E-Commerce Customer Support Agent

An Agentic AI customer support system built with Python using Tools, Stateful Session Memory, and RAG architecture.

## Features
- **Dynamic Tool Calling**: Checks order status, searches product catalogs, and handles returns.
- **Business Rule Validation**: Enforces return policies (e.g., items must be delivered).
- **Persistent State**: Retains user profile, name, and history across sessions via `memory_store.json`.
- **Hybrid Architecture**: Runs seamlessly online with LLM APIs and offline with a deterministic rule engine.

## Project Structure
- `ecommerce_agent.py`: Core agent architecture and tool-calling implementation.
- `memory_store.json`: Persistent user memory storage.
- `AI_Ecommerce_Agent_Cleaned_Report_Mari_Anu.docx`: Comprehensive project documentation.

## How to Run
```bash
python ecommerce_agent.py
