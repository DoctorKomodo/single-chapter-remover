FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gosu \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fix_single_chapters.py .

# Build-time placeholder user. Deleted and recreated at container start with
# the correct PUID/PGID, so the exact IDs here do not matter.
RUN useradd -M -d /app -s /usr/sbin/nologin appuser

ENV PUID=1000
ENV PGID=1000
ENV PYTHONUNBUFFERED=1

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "fix_single_chapters.py"]
