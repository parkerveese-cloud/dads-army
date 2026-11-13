ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:3.23
FROM ${BUILD_FROM}

# Python's standard library is all Dads Army needs (tzdata so "today" is your local date).
RUN apk add --no-cache python3 tzdata

WORKDIR /app
COPY server.py intel.py /app/
COPY static /app/static

# /data is the add-on's own storage: it survives restarts and updates
# and is included in Home Assistant backups.
ENV DADSARMY_DATA=/data \
    DADSARMY_PORT=8080 \
    DADSARMY_HOMEASSISTANT=1 \
    PYTHONUNBUFFERED=1

# Plain process under Docker's own init (the base image's s6 isn't needed).
ENTRYPOINT []
CMD ["python3", "/app/server.py"]
