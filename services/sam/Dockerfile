# Optional MuseBreak helper — loads a real Hugging Face model.
# No official Docker Hub image was verified for this model; we build locally.
# Model: facebook/sam2.1-hiera-large
# SAM 2.1 (ungated). HF also has gated facebook/sam3 and facebook/sam3.1 — not defaulted here.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx transformers torch --extra-index-url https://download.pytorch.org/whl/cpu
COPY app.py .
ENV HF_MODEL_ID=facebook/sam2.1-hiera-large
ENV PORT=8091
EXPOSE 8091
CMD ["python", "app.py"]
