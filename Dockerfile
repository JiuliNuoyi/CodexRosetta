# ---- Stage 1: Build frontend ----
FROM node:22-alpine AS web-builder

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- Stage 2: Runtime ----
FROM python:3.12-slim

WORKDIR /app

# Copy project definition and source first
COPY pyproject.toml README.md LICENSE THIRD_PARTY_LICENSES.md ./
COPY codex_rosetta/ codex_rosetta/

# Copy built frontend from Stage 1 (needed by pip install due to force-include)
COPY --from=web-builder /build/web/dist/ web/dist/

# Install (includes the package itself and web/dist)
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data

# Default environment
ENV HOST=0.0.0.0
ENV PORT=33131

EXPOSE 33131

VOLUME /app/data

ENTRYPOINT ["python", "-m", "codex_rosetta.main"]
