# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GNS3 Copilot is an AI-powered network automation assistant for GNS3 network simulator. Users interact via natural language through a Streamlit web UI to configure devices, manage topologies, and troubleshoot networks.

## Commands

```bash
make install      # Install dev dependencies (pip install -e ".[dev]")
make lint         # ruff check --fix + ruff format (src/ only)
make type-check   # mypy src (strict mode, Python 3.13)
make test         # pytest with coverage
make check        # lint + type-check + test (run before commits)

# Run a single test
pytest tests/agent/test_topology_dry_run.py::test_parse_bool_variants

# Run app
streamlit run src/gns3_copilot/main.py
```

## Architecture

**Layered design with strict separation of concerns:**

1. **UI Layer** (`src/gns3_copilot/ui_model/`) — Streamlit components. Display and user interaction only, no business logic. Uses Material Design icons (`:material:*:` prefix).

2. **Agent Layer** (`src/gns3_copilot/agent/`) — LangGraph StateGraph workflow orchestrating LLM calls and tool invocation. Nodes: `llm_call` → `tool_node` → `title_generator`. State persisted via SQLite checkpointer (`langgraph-checkpoint-sqlite`). Supports dry-run simulation mode for topology operations.

3. **Tool Layer** (`src/gns3_copilot/tools_v2/`) — LangChain tool definitions. Tools only define interfaces and call into lower layers; no business logic here. Includes Nornir-based config/display/Linux commands, VPCS tools (telnetlib3), and GNS3 node/link/drawing management.

4. **GNS3 Client** (`src/gns3_copilot/gns3_client/`) — Custom enhanced gns3fy client wrapping the GNS3 REST API. Must support both API v2 and v3 (v3 adds authentication).

5. **Prompts** (`src/gns3_copilot/prompts/`) — LLM prompt templates with multilingual support and English proficiency levels. Includes specialized flows for FortiGate configuration with quality review and validation.

6. **Configuration** (`src/gns3_copilot/utils/app_config.py`) — SQLite-backed key-value config store (`get_config`/`set_config`/`init_config`). 80+ settings covering GNS3 server, LLM provider, voice, UI preferences. Loaded into `streamlit.session_state` at startup.

**Key patterns:**
- **Model Factory** (`agent/model_factory.py`): Creates fresh LLM instances on-demand with HTTP tracing and tool binding. Supports OpenAI, Anthropic, DeepSeek, XAI, Google, AWS Bedrock, Ollama, OpenRouter.
- **Dry-run simulation** (`agent/topology_dry_run.py`): Topology operations can simulate without calling GNS3 API.
- **Connector Factory** (`gns3_client/connector_factory.py`): Creates GNS3 API connectors handling v2/v3 differences.

## Code Style & Conventions

- Python 3.10+. PEP 8 with 88-char line length (black/ruff).
- Type annotations required for public functions. mypy strict mode.
- Functions should not exceed ~50 lines. Max 4 levels of nesting; use early returns.
- Bilingual docstrings (English + Chinese) are common in this codebase.
- Network operations must set timeouts and implement retry logic.
- Tool functions should be idempotent.
- Do not run or fix tests unless explicitly requested.
- Run `make lint` and `make type-check` after code modifications.

## Test Structure

Tests mirror source layout under `tests/` (e.g., `tests/agent/`, `tests/gns3_client/`, `tests/tools_v2/`). Shared fixtures in `tests/conftest.py` provide `mock_env`, `mock_gns3_v2_env`, and `mock_gns3_v3_env` for environment setup.
