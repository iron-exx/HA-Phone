ARG BUILD_FROM=ghcr.io/hassio-addons/debian-base:7.3.0

# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM ${BUILD_FROM} AS build

ARG ASTERISK_VERSION=22.10.1

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    binutils-dev \
    build-essential \
    ca-certificates \
    curl \
    git \
    libcurl4-openssl-dev \
    libedit-dev \
    libgsm1-dev \
    libjansson-dev \
    libogg-dev \
    libopus-dev \
    libopusfile-dev \
    libresample1-dev \
    libspeexdsp-dev \
    libsqlite3-dev \
    libssl-dev \
    libunbound-dev \
    libuuid1 \
    libxml2-dev \
    libxslt1-dev \
    pkg-config \
    python3-dev \
    subversion \
    unixodbc-dev \
    uuid-dev \
    wget \
  && rm -rf /var/lib/apt/lists/*

# (Frontend is built in a separate `frontend-build` stage — no Node.js needed here.)

WORKDIR /usr/src

RUN wget -q "https://downloads.asterisk.org/pub/telephony/asterisk/asterisk-${ASTERISK_VERSION}.tar.gz" \
    && tar xzf "asterisk-${ASTERISK_VERSION}.tar.gz" \
    && rm "asterisk-${ASTERISK_VERSION}.tar.gz"

WORKDIR /usr/src/asterisk-${ASTERISK_VERSION}

RUN ./configure \
    --with-jansson-bundled \
    --with-pjproject-bundled \
    --with-opus \
    --with-opusfile \
    --with-resample \
    --with-unbound \
    --without-asound \
    --without-bluetooth \
    --without-dahdi \
    --without-gtk2 \
    --without-jack \
    --without-portaudio \
    --without-postgres \
    --without-pri \
    --without-radius \
    --without-sdl \
    --without-ss7 \
    --without-tds \
    --without-unixodbc \
    --without-x11 \
    --disable-native-build \
    --prefix=/usr

RUN make menuselect.makeopts && \
    menuselect/menuselect \
      --disable-all \
      --enable res_pjproject \
      --enable res_resolver_unbound \
      --enable res_sorcery_config \
      --enable res_sorcery_memory \
      --enable res_sorcery_astdb \
      --enable res_geolocation \
      --enable res_statsd \
      --enable res_rtp_asterisk \
      --enable res_pjsip \
      --enable res_pjsip_authenticator_digest \
      --enable res_pjsip_outbound_authenticator_digest \
      --enable res_pjsip_endpoint_identifier_anonymous \
      --enable res_pjsip_endpoint_identifier_ip \
      --enable res_pjsip_endpoint_identifier_user \
      --enable res_pjsip_logger \
      --enable res_pjsip_notify \
      --enable res_pjsip_outbound_registration \
      --enable res_pjsip_path \
      --enable res_pjsip_registrar \
      --enable res_pjsip_sdp_rtp \
      --enable res_pjsip_session \
      --enable res_pjsip_pubsub \
      --enable chan_pjsip \
      --enable res_http_websocket \
      --enable res_stasis \
      --enable res_stasis_answer \
      --enable res_stasis_device_state \
      --enable res_stasis_playback \
      --enable res_stasis_recording \
      --enable res_stasis_snoop \
      --enable app_dial \
      --enable app_echo \
      --enable app_playback \
      --enable app_voicemail \
      --enable res_adsi \
      --enable res_smdi \
      --enable bridge_simple \
      --enable bridge_softmix \
      --enable bridge_native_rtp \
      --enable bridge_holding \
      --enable func_callerid \
      --enable func_channel \
      --enable func_strings \
      --enable func_logic \
      --enable res_musiconhold \
      --enable codec_alaw \
      --enable codec_ulaw \
      --enable codec_g722 \
      --enable format_wav \
      --enable format_wav_gsm \
      --enable pbx_config \
      --enable cdr_csv \
      menuselect.makeopts

RUN make -j1 third-party && \
    make -j$(nproc) all && \
    make install DESTDIR=/opt/asterisk && \
    rm -rf /opt/asterisk/var/run

# ── Stage 1b: Frontend build ────────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build
# Outputs: /app/frontend/dist/

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM ${BUILD_FROM}

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Berlin

RUN ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    iproute2 \
    libcurl4 \
    libedit2 \
    libgsm1 \
    libogg0 \
    libopus0 \
    libresample1 \
    libspeexdsp1 \
    libsqlite3-0 \
    libssl3 \
    libunbound8 \
    libuuid1 \
    libxml2 \
    libxslt1.1 \
    netcat-openbsd \
    python3 \
    python3-pip \
    msmtp \
    sngrep \
    sox \
    tcpdump \
    uuid-runtime \
  && rm -rf /var/lib/apt/lists/*

# Copy compiled Asterisk from build stage
COPY --from=build /opt/asterisk/ /

# Install Python backend dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /app/backend/requirements.txt

# Copy backend source
COPY backend/ /app/backend/

# Copy compiled frontend bundle from frontend build stage
COPY --from=frontend-build /app/frontend/dist/ /app/frontend/dist/

# Create required runtime directories
RUN mkdir -p \
    /var/run/asterisk \
    /var/log/asterisk \
    /var/lib/asterisk \
    /var/spool/asterisk \
    /etc/asterisk

# Copy rootfs (s6 scripts + Asterisk configs)
COPY rootfs /

# Ensure s6 service scripts are executable
RUN chmod +x \
    /etc/cont-init.d/10-asterisk-init.sh \
    /etc/services.d/asterisk/run \
    /etc/services.d/asterisk/finish \
    /etc/services.d/fastapi/run \
    /etc/services.d/fastapi/finish

HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --retries=3 \
  --start-period=30s \
  --start-interval=5s \
  CMD asterisk -rx "core waitfullybooted" 2>/dev/null || exit 1
