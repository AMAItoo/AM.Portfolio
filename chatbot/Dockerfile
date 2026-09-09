# Portfolio Chatbot — Hugging Face Space Docker image
# SDK=Docker, port 7860, CPU free tier.
# Build context = repository root (so the whole repo can be git-pushed
# to a HF Space and the Dockerfile resolves). Depends: Dockerfile at repo
# root would also work; you can push the whole repo as the Space.
#
# To use as a Space: create an empty Docker Space, then either
#   a) docker build -t pf-chatbot . && docker push (custom), or
#   b) the canonical path — push this repo to the Space via git,
#      and the Space's own Dockerfile at chatbot/Dockerfile must be
#      moved to root. This layout documents that step; see README.
FROM python:3.11-slim

WORKDIR /app

# torch CPU wheels are much smaller than the default CUDA build.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY chatbot/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# App package + bilingual knowledge base (indexed at startup)
COPY chatbot/ /app/chatbot/

ENV PORT=7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=5)" || exit 1

CMD ["uvicorn", "chatbot.app:app", "--host", "0.0.0.0", "--port", "7860"]