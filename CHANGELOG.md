# Changelog

All notable changes to this project will be documented in this file.

## [v6.0.0] - 2026-08-20
### Added
- **Google ADK & AEBOP™ Standard Core Architecture**:
  - Implemented `ADKAgentRunner` with controlled cognitive orchestration and GPU resource locking.
  - Standardized all tools via typed Pydantic models (`NormalizeFileInput`, `TranscribeAudioInput`, `RefineTranscriptInput`, `GenerateProtocolInput`, `VerifyProtocolInput`, `GenerateDocxInput`, `SendEmailInput`).
  - Added centralized `TOOLS_REGISTRY`, JSON function declarations generator, and unified `execute_tool_call()` dispatcher.
  - Implemented ADK lifecycle hooks `before_tool_callback` (pre-flight checks, prompt injection guardrails, email validation) and `after_tool_callback` (OpenInference / OpenTelemetry standardized telemetry).
  - Introduced interactive **Approval Gate** for irreversible actions (`POST /approve/{file_id}`).
  - Separated memory models into `SessionContext` and `MeetingState`.
- **Quality Flywheel & Continuous Evaluation**:
  - Configured `tests/eval/eval_config.yaml` with 95.0% pass rate threshold.
  - Created `golden_protocols.json` multi-turn meeting benchmark dataset.
  - Added automated evaluation runner `evals/run_regression_evals.py` (99.6% benchmark score achieved).
  - Added ADK compliance test suite `tests/test_adk_compliance.py`.

## [v5.8.0] - 2026-06-01
### Added
- Universal running capability (works both natively on Windows via `.bat` and inside Docker via `docker-compose`).
- Added environment variable override in `docker-compose.yml` and `docker-compose.cpu.yml` for `OLLAMA_URL` to point to the `ollama` container, allowing `.env` to default to `127.0.0.1` for native setups.
