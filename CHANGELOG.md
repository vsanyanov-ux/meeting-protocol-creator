# Changelog

All notable changes to this project will be documented in this file.

## [v5.8.0] - 2026-06-01
### Added
- Universal running capability (works both natively on Windows via `.bat` and inside Docker via `docker-compose`).
- Added environment variable override in `docker-compose.yml` and `docker-compose.cpu.yml` for `OLLAMA_URL` to point to the `ollama` container, allowing `.env` to default to `127.0.0.1` for native setups.
