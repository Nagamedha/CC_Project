# ----------------------------------------------------------------
# Stage 1: BUILD (Install dependencies separately)
# ----------------------------------------------------------------
FROM python:3.9-slim AS build

# 1) Install build tools / system dependencies (only needed at build time)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 2) Copy and install dependencies separately (so they get cached!)
COPY requirements.txt .
RUN pip install --no-cache-dir --target /lambda_dependencies -r requirements.txt

# ----------------------------------------------------------------
# Stage 2: RUNTIME (Final optimized image)
# ----------------------------------------------------------------
FROM python:3.9-slim

# If runtime needs OpenBLAS, etc.:
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /var/task

# 3) Copy pre-installed dependencies from build stage (✅ Cached)
COPY --from=build /lambda_dependencies /var/task/

# 4) Install AWS Lambda Runtime Interface Client (only needed once)
RUN pip install --no-cache-dir awslambdaric

# 5) **Copy your application code LAST (so this step invalidates only when necessary)**
COPY file_processor/ /var/task/file_processor/

# 6) Set environment & entrypoint
ENV PYTHONPATH=/var/task
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["file_processor.src.routing_lambda.main_router_lambda.lambda_handler"]