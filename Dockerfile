FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e .

ENV MW_AGENT=miniagent_like
ENV MW_PROVIDER=minimax
ENV MW_MODEL=MiniMax-M2.5
ENV MW_WORKSPACE=/workspace
ENV MW_SESSION=default
ENV OPENAI_API_KEY=sk-cp-lbBYfoPeTkxUZ18aprKaHKCVaBP6oAdy7pgGaq5fxlTiTblymkuiWokY8ai9oNRRCDXmd2qW-DkTGZBtFtR6hhJfPZZrD62I8WuxCICr0cQIEKtd5uOwtdY
ENV OPENAI_BASE_URL=https://api.minimaxi.com/v1

ENTRYPOINT ["python", "-m", "mini_worker.cli"]
CMD ["--help"]
