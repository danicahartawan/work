# Perch server with NVIDIA's open-source speech stack (GPU).
# Build:  docker build -t perch-server server/
# Run:    docker run --gpus all -p 8000:8000 -v perch-data:/data perch-server
FROM nvcr.io/nvidia/pytorch:24.12-py3

WORKDIR /srv
COPY requirements.txt requirements-nemo.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-nemo.txt

COPY app ./app

ENV PERCH_DATA_DIR=/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
