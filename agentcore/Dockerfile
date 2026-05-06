# AgentCore Runtime requires ARM64 containers.
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.13-slim

WORKDIR /app

# Install deps first so layer cache survives source edits.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY agent_handler.py /app/agent_handler.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# AgentCore expects the app on 0.0.0.0:8080 with /invocations + /ping endpoints.
# BedrockAgentCoreApp.run() handles all of that.
CMD ["python", "/app/agent_handler.py"]
