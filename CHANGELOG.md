# Changelog

All notable changes to this project will be documented in this file.

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
