# Repository Instructions

## Code Comments

- For all newly added or modified code, add explanatory comments by default when the intent is not obvious.
- Comments must be easy to read and should explain why the code exists, what constraints it handles, and any important edge cases.
- Use bilingual comments in Chinese and English for important logic, non-obvious branches, protocol handling, data transformations, and tricky validation rules.
- Avoid low-value comments that only restate the code literally. Simple assignments and obvious control flow do not need comments.
- Prefer short, direct comments placed near the relevant logic. Keep wording clear enough that a new contributor can understand the intent quickly.

## Project Overview

GNS3 Copilot is an AI-powered network automation assistant for GNS3 network simulator. Users interact via natural language through a Streamlit web UI to configure devices, manage topologies, and troubleshoot networks.

## Development Commands

- `make install` — Install dev dependencies (pip install -e ".[dev]")
- `make lint` — Run ruff check --fix and ruff format on src/ directory
- `make type-check` — Run mypy src in strict mode (Python 3.13)
- `make test` — Run pytest with coverage
- `make check` — Run lint, type-check, and test (run before commits)
- `pytest tests/agent/test_topology_dry_run.py::test_parse_bool_variants` — Run a single test
- `streamlit run src/gns3_copilot/main.py` — Run the application

## Architecture

The codebase follows a layered design with strict separation of concerns:

**UI Layer** (`src/gns3_copilot/ui_model/`) — Streamlit components for display and user interaction only. Contains no business logic. Uses Material Design icons with `:material:*:` prefix.

**Agent Layer** (`src/gns3_copilot/agent/`) — LangGraph StateGraph workflow that orchestrates LLM calls and tool invocation. Workflow nodes: `llm_call` → `tool_node` → `title_generator`. State is persisted via SQLite checkpointer (`langgraph-checkpoint-sqlite`). Supports dry-run simulation mode for topology operations to test without calling the GNS3 API.

**Tool Layer** (`src/gns3_copilot/tools_v2/`) — LangChain tool definitions that define interfaces and call into lower layers. Contains no business logic. Includes Nornir-based config/display/Linux commands, VPCS tools (telnetlib3), and GNS3 node/link/drawing management.

**GNS3 Client** (`src/gns3_copilot/gns3_client/`) — Custom enhanced gns3fy client wrapping the GNS3 REST API. Must support both API v2 and v3 (v3 adds authentication).

**Prompts** (`src/gns3_copilot/prompts/`) — LLM prompt templates with multilingual support and English proficiency levels. Includes specialized flows for FortiGate configuration with quality review and validation.

**Configuration** (`src/gns3_copilot/utils/app_config.py`) — SQLite-backed key-value config store with `get_config`, `set_config`, and `init_config` functions. Manages 80+ settings covering GNS3 server, LLM provider, voice, and UI preferences. Configuration is loaded into `streamlit.session_state` at startup.

**Key Patterns:**
- Model Factory (`agent/model_factory.py`) creates fresh LLM instances on-demand with HTTP tracing and tool binding. Supports OpenAI, Anthropic, DeepSeek, XAI, Google, AWS Bedrock, Ollama, and OpenRouter.
- Dry-run simulation (`agent/topology_dry_run.py`) allows topology operations to simulate without calling the GNS3 API.
- Connector Factory (`gns3_client/connector_factory.py`) creates GNS3 API connectors that handle v2/v3 differences.

## Code Style & Conventions

- Python 3.10+. Follow PEP 8 with 88-character line length (black/ruff).
- Type annotations are required for public functions. Use mypy strict mode.
- Functions should not exceed approximately 50 lines. Maximum 4 levels of nesting; use early returns.
- Bilingual docstrings (English + Chinese) are common in this codebase.
- Network operations must set timeouts and implement retry logic.
- Tool functions should be idempotent.
- Do not run or fix tests unless explicitly requested.
- Run `make lint` and `make type-check` after code modifications.

## Test Structure

Tests mirror the source layout under `tests/` (for example, `tests/agent/`, `tests/gns3_client/`, `tests/tools_v2/`). Shared fixtures in `tests/conftest.py` provide `mock_env`, `mock_gns3_v2_env`, and `mock_gns3_v3_env` for environment setup.
