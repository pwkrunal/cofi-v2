# Cofi Layer Python Service - Task Checklist

## Planning
- [x] Review `cofi-layer-flow.txt` requirements
- [x] Review `API_DETAILS.md` for API specifications
- [x] Review `schema.txt` for database schema
- [x] Create implementation plan
- [x] Get user approval

## cofi-service (CPU Orchestrator)
- [x] Project setup (Dockerfile, docker-compose.yml, requirements.txt, .env.example)
- [x] `config.py` - Pydantic settings with IVR_ENABLED, CALLMETADATA_ENABLED, TRADEMETADATA_ENABLED
- [x] `database.py` - mysql.connector with connection pooling, repositories (BatchStatus, FileDistribution, LidStatus, Call, Language, Process)
- [x] `file_manager.py` - Batch file reading, round-robin GPU distribution
- [x] `rule_engine.py` - Trade to Audio matching logic (Step 1)
- [x] Update `main.py` with Rule Engine and Configurable LLM stages
- [x] Update `stt_stage.py` with Language filtering and Transcript storage
- [x] Update `llm1_stage.py` with Transcript/Trade extraction and storage
- [x] Create `query_audit_form.py` helper script

## Pipeline Stages
- [x] File distribution to GPUs
- [x] CallMetadata CSV upload (optional)
- [x] TradeMetadata CSV upload (optional)
- [x] `pipeline/ivr_stage.py` - IVR processing (optional)
- [x] `pipeline/lid_stage.py` - Language identification
- [x] `pipeline/stt_stage.py` - Speech-to-text
- [x] `pipeline/llm1_stage.py` - First LLM extraction
- [x] `pipeline/llm2_stage.py` - Second LLM extraction

## cofi-mediator-service (GPU Helper)
- [x] `app.py` - FastAPI with file upload, container control endpoints
- [x] `docker_service.py` - Docker SDK wrapper using docker.from_env()
- [x] Dockerfile and docker-compose.yml with Docker socket mount

## Verification
- [ ] Deploy to GPU machines
- [ ] Test end-to-end pipeline
- [ ] Verify resume functionality
