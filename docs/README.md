# AIseek Trae v1 (Fusion Enhanced)

## Overview
AIseek is a platform that automatically generates short educational videos from long-form text.
This version uses a single FastAPI backend (serves API + UI) and Celery workers for AI rendering and video transcode pipelines.

## Architecture
- **Backend**: FastAPI + Jinja2 + Postgres (API + UI, stateless)
- **Workers**: Celery (ai/transcode queues) + Redis broker (async jobs, scalable)
- **Features**:
  - DeepSeek Text Analysis
  - Edge-TTS Voiceover
  - Background Music Mixing (New!)
  - AI Image Fetching (Pollinations.ai) (New!)
  - Hardware Accelerated Video Encoding

## Quick Start
See [DEPLOY.md](DEPLOY.md) for detailed instructions.

## Docs
- [DEPLOY.md](DEPLOY.md)
- [BACKUP.md](BACKUP.md)
- [BILLION_SCALE_AUDIT.md](BILLION_SCALE_AUDIT.md)
- [OPS_STAGE2.md](OPS_STAGE2.md)
- [BLUEPRINT.md](BLUEPRINT.md)
- [SCALE.md](SCALE.md)
- [API.md](API.md)
- [WORKER_CALLBACK.md](WORKER_CALLBACK.md)
- [AI_STUDIO_ARCH.md](AI_STUDIO_ARCH.md)
- [LOCAL_AI_STUDIO.md](LOCAL_AI_STUDIO.md)

## Directory Structure
- `backend/`: FastAPI backend (API + UI)
- `worker/`: Celery workers (AI render + transcode)
- `scripts/`: Helper scripts
- `docs/`: Documentation
