# Optional MuseBreak helper — loads a real Hugging Face model.
# No official Docker Hub image was verified for this model; we build locally.
# Model: facebook/seamless-m4t-v2-large
# SeamlessM4T v2 large speech/text translation.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx transformers torch --extra-index-url https://download.pytorch.org/whl/cpu
COPY app.py .
ENV HF_MODEL_ID=facebook/seamless-m4t-v2-large
ENV PORT=8093
EXPOSE 8093
CMD ["python", "app.py"]
