ARG BUILD_FROM=ghcr.io/home-assistant/base:3.23
FROM ${BUILD_FROM}

LABEL \
  io.hass.name="Wallbox-Dolibarr Addon" \
  io.hass.description="Erfassung und Übertragung von Wallbox-Ladevorgängen" \
  io.hass.type="addon" \
  io.hass.version="1.1.0" \
  org.opencontainers.image.source="https://github.com/user/Wallbox-Dolibarr"

# Alpine Pakete installieren
RUN apk add --no-cache python3 py3-pip py3-requests sqlite

# Python Abhängigkeiten
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Addon Dateien kopieren
COPY main.py /usr/local/bin/main.py
COPY session_manager.py /usr/local/bin/session_manager.py
COPY api_client.py /usr/local/bin/api_client.py
COPY dashboard.py /usr/local/bin/dashboard.py
COPY utils/ /usr/local/bin/utils/
RUN chmod a+x /usr/local/bin/main.py

# HA Ingress Port
EXPOSE 8099

CMD ["python3", "/usr/local/bin/main.py"]
