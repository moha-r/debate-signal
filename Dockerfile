FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package*.json frontend/
COPY landing/package*.json landing/
RUN npm --prefix frontend ci --no-audit --no-fund \
    && npm --prefix landing ci --no-audit --no-fund
COPY frontend/ frontend/
COPY landing/ landing/
RUN npm --prefix frontend run build && npm --prefix landing run build

FROM python:3.13-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/debate-models HF_HUB_DISABLE_XET=1 \
    DATA_DIR=/var/lib/debate-signal ARGUMENT_RELATION_BACKEND=transformer

COPY requirements.txt requirements-voice.txt ./
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu 'torch==2.15.0+cpu' \
    && pip install --no-cache-dir -r requirements-voice.txt 'transformers==5.23.0' \
    && useradd --system --user-group debate \
    && install -d -m 0700 -o debate -g debate "$DATA_DIR" "$HF_HOME"

COPY answer_extraction.py argument_link_selector.py argument_models.py auth_store.py conversation_insights.py dialogue_relations.py \
    local_dashboard.py moderation_session.py nlp_pipeline.py prepare_dialogue_relation_model.py \
    question_tracker.py relation_context.py session_store.py topic_relevance.py voice_gateway.py ./
COPY artifacts/LinearSVC_alert.joblib artifacts/argument_models_v2.joblib \
    artifacts/dialogue_relation_policy.json artifacts/contextual_link_selector.joblib artifacts/ARGUMENT_MODEL_NOTICE.md artifacts/
COPY results/topic_policy.json results/
COPY --from=frontend-build /build/frontend/dist/ frontend/dist/
COPY --from=frontend-build /build/landing/dist/ landing/dist/

USER debate
RUN python prepare_dialogue_relation_model.py && python answer_extraction.py \
    && python -c 'from moderation_session import new_session; new_session("Should schools require uniforms?")'
ENV HF_HUB_OFFLINE=1
EXPOSE 7863
CMD ["uvicorn", "local_dashboard:app", "--host", "0.0.0.0", "--port", "7863", "--workers", "1", "--ws-max-size", "8192"]
