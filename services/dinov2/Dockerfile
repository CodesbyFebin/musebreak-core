# Optional MuseBreak helper — loads a real Hugging Face model.
# No official Docker Hub image was verified for this model; we build locally.
# Model: facebook/dinov2-giant
# DINOv2 giant vision backbone.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx transformers torch --extra-index-url https://download.pytorch.org/whl/cpu
COPY app.py .
ENV HF_MODEL_ID=facebook/dinov2-giant
ENV PORT=8092
EXPOSE 8092
CMD ["python", "app.py"]
