# Changelog

All notable changes to this project will be documented in this file.
 
## [4.0.0] — 2026-04-16

### Added
- **Enterprise Robustness**: Implemented a 3-tier hardware fallback: **GPU (CUDA) → CPU → Cloud (Yandex)**. Automatically switches processing mode if resources are exhausted or unavailable.
- **Smart Diarization**:
    - **Cloud v2**: Native speaker separation for long recordings via Yandex SpeechKit LongRunning API.
    - **AI-Linguistic**: Context-aware speaker identification for short clips via LLM post-processing.
- **AI-Auditor 2.0**: The Auditor's quality report (completeness, accuracy, hallucinations) is now embedded directly into the final DOCX protocol.
- **Enterprise Monitoring**: Added automated scoring (1-5 stars) from the AI-Auditor to the Langfuse dashboard.
- **Pilot Tracker**: New corporate tool for tracking ROI and quality metrics across pilot projects.

### Improved
- **UI/UX Rebranding**: Unified system status badge (Backend/LLM) and transitioned all AI terminology to **LLM**.
- **Observability**: Fully migrated to **Langfuse SDK v4** with stable trace IDs and granular error reporting.
- **Performance**: Optimized Faster-Whisper DLL loading on Windows and fixed VRAM contention during model switching.

### Fixed
- **Connectivity**: Resolved "All connection attempts failed" bug when communicating with local Ollama on Windows.
- **Backend Stability**: Fixed critical race conditions in the multi-provider routing logic.

## [3.1.0] — 2026-04-16
 
### Changed
- **Rebranding**: Officially renamed the project from **PRO-Толк** to **Протоколист**. Updated all documentation, branding, and UI components.
 
## [3.0.0] — 2026-04-15
 
### Added
- **Turbo Mode (GPU Acceleration)**: Full NVIDIA CUDA support for both **Faster-Whisper** and **Ollama**.
- **Model Persistence**: Implemented a "warm model" strategy where AI models stay resident in VRAM, reducing end-to-end latency for subsequent requests.
- **Enhanced Observability**: Added granular `transcription` tracing to the Langfuse dashboard to monitor Whisper performance.
- **Hardware Optimization**: Fine-tuned the pipeline for consumer GPUs (RTX 3060 12GB) and WSL2 environments with resource constraints.
 
### Improved
- **Pipeline Speed**: Achieved a **3.5x speedup** for local processing (from ~5m down to <1.5m for standard clips).
- **Stability**: Resolved critical VRAM contention and OOM crashes by streamlining model lifecycle management.
- **Docker Integration**: Simplified GPU reservation logic in `docker-compose.yml`.
 
### Changed
- **Default STT**: Switched default local transcription model to `small` (cuda) for the optimal quality/speed ratio.

## [2.1.3] — 2026-04-11

### Added
-   **Rebranding**: Officially renamed the project to **PRO-Толк** (AI Protocol Assistant). Updated UI titles, subtitles, and documentation.
-   **Accurate Cost Mapping**: Implemented 92 RUB/USD exchange rate for Yandex Cloud AI services to ensure correct cost tracking in the Langfuse dashboard.
-   **Dynamic Model Indicators**: Updated frontend buttons to show "Local" or "Online" status based on the selected AI provider.

### Fixed
-   **Langfuse SDK v4 Hardening**: Resolved critical ID validation conflicts by separating 32-hex Trace IDs and 16-hex Span IDs. Fixed trace nesting using `trace_context`.
-   **STT Pricing**: Implemented duration-based pricing for transcription logs.


## [2.1.2] — 2026-04-10

### Added
-   **Strict Observability Filtering**: Implemented `should_export_span` filter in the Langfuse client to eliminate auto-instrumentation noise from third-party libraries (httpx, etc.).
-   **Automated Cleanup**: Created a utility script for batch deleting junk traces from the Langfuse dashboard.

### Fixed
-   **Langfuse v4 Compatibility**: Fixed critical hex ID formatting error and implemented v4-compatible trace initialization using `trace_context`.

### Improved
-   **Email Antispam**: Added `Auto-Submitted` and `X-Auto-Response-Suppress` headers to reduce spam scores and prevent auto-reply loops.

## [2.1.1] — 2026-04-10

### Fixed
-   **Langfuse v4 (OpenTelemetry) Compatibility**: Fixed critical `ValueError` in trace initialization by switching to 32-bit hex IDs (without dashes) and better attribute handling.
-   **SMTP Deliverability**: Resolved error `554 5.7.1 Message rejected under suspicion of SPAM` for Yandex. Added proper `Message-ID`, `Date`, and HTML content to outgoing emails.
-   **Backend Robustness**: Fixed indentation issues and improved error handling in the main processing pipeline. Status updates now continue even if optional steps (like emailing) fail.

### Changed
-   **Observability**: Renamed trace root for clearer identification in Langfuse.
-   **Security**: Synchronized sender identity with verified SMTP credentials to improve mail server trust.

## [2.1.0] — 2026-04-10

### Added
-   **Email Notifications**: Initial deployment of the email delivery system using Yandex SMTP with SSL/TLS support.

## [2.0.0] — 2026-04-09

### Added
- **Offline / Local Mode**: Full support for local execution using **Ollama** and **Faster-Whisper**. Integrated **Qwen 2.5 (3B)** as the default local LLM.
- **Hybrid AI Router**: Ability to switch between Yandex Cloud and Local providers via `.env` configuration or dedicated `.bat` scripts.
- **Langfuse Observability**: Major transition to Langfuse SDK v4 for tracing all pipeline stages, including transcription, generation, and verification.
- **Cost Estimation**: Integrated cost and token usage tracking for both Yandex and local providers within the tracing dashboard.
- **AI-Auditor (Self-Critique)**: Automated verification mechanism that audits the generated protocol against the original transcription to prevent hallucinations.
- **Smart Tables**: Enhanced protocol formatting with automatic Markdown/Word table generation for action items and decisions.
- **Environment Management**: Added `switch_to_local.bat` and `switch_to_yandex.bat` for quick environment setup.

### Fixed
- **Pipeline Data Loss**: Fixed a critical bug where transcription and auditing results were not persisted correctly during the final protocol generation step.
- **Trace Missing Steps**: Resolved an issue where Langfuse traces were only recorded for certain actions, leaving gaps in the observability history.
- **Local STT Stability**: Improved error handling and resource management for long-duration audio transcriptions on CPU/GPU.
- **Validation Errors**: Fixed Pydantic model discrepancies when switching between different LLM providers with varying output formats.

## [1.0.0] - 2026-04-04

### Added
- **Core Engine**: Automated meeting summarization using YandexGPT and Yandex SpeechKit.
- **Multi-format Support**: Capability to process Audio (MP3, WAV, M4A, etc.), Video (MP4, WEBM), and Documents (PDF, DOCX, TXT).
- **Professional Outputs**: Automatic generation of formatted DOCX protocols with structured tables for action items.
- **AI-Auditor**: Built-in verification mechanism (Self-Critique) where the AI audits its own protocol against the transcription for accuracy.
- **Hybrid Diarization**: Smart speaker separation that works even without complex S3 bucket configurations.
- **UI/UX**: Modern, premium React frontend with glassmorphism, smooth animations (Framer Motion), and real-time status polling.
- **Robust CI/CD**: Consolidated GitHub Actions pipeline for both backend and frontend testing.
- **Testing Suite**: Added Vitest and React Testing Library for frontend stability.
- **Docker Production Ready**: Optimized Multi-stage Dockerfiles for both services and Nginx proxy configuration.
