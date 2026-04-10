# Changelog

All notable changes to this project will be documented in this file.

## [2.1.1] — 2026-04-10

### Fixed
-   **Langfuse v4 (OpenTelemetry) Compatibility**: Fixed critical `ValueError` in trace initialization by switching to 32-bit hex IDs (without dashes) and better attribute handling.
-   **SMTP Deliverability**: Resolved error `554 5.7.1 Message rejected under suspicion of SPAM` for Yandex. Added proper `Message-ID`, `Date`, and HTML content to outgoing emails.
-   **Backend Robustness**: Fixed indentation issues and improved error handling in the main processing pipeline. Status updates now continue even if optional steps (like emailing) fail.

### Changed
-   **Observability**: Renamed trace root for clearer identification in Langfuse.
-   **Security**: Synchronized sender identity with verified SMTP credentials to improve mail server trust.

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
