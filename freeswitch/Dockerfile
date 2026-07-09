# syntax=docker/dockerfile:1
#
# Build mod_audio_stream (amigniter/mod_audio_stream, MIT) fora da árvore
# contra os headers do FreeSWITCH 1.11.x e copia o .so compilado + libs de
# runtime para a imagem vanilla já usada pelo projeto
# (safarov/freeswitch:1.10.12), preservando conf/dialplan existentes.
#
# Substitui mod_audio_fork (feature 007-audio-stream-migration): o
# repositório de origem (drachtio/drachtio-freeswitch-modules) foi
# descontinuado. mod_audio_stream cumpre o mesmo papel (streaming de áudio
# via WebSocket) e está ativamente mantido.
#
# Redução de dependência externa: os .deb de libfreeswitch1/libfreeswitch-dev
# ficam vendorizados em freeswitch/vendor/debs/ (fora do git — grandes demais
# e binários, mesmo padrão de freeswitch/signalwire_token.txt), baixados uma
# única vez com o token abaixo. Rebuilds futuros usam os .deb vendorizados
# por padrão; o fallback via repositório SignalWire só é necessário se a
# versão do FreeSWITCH mudar e os .deb precisarem ser atualizados.
#
# Repositório APT da SignalWire (fallback, só necessário para atualizar os
# .deb vendorizados) exige uma conta + token pessoal desde a migração do
# repo público (o antigo login de convidado não existe mais). A URL antiga
# de cadastro (id.signalwire.com/signup/account/new) está morta. O token
# válido é um "Personal Access Token" (prefixo pat_), gerado no painel da
# SignalWire — não confundir com o Project Token (PT...)/SignIn Key (PSK_...)
# do Space, que são para as APIs de voz/vídeo, não para este repositório.
#   docker build --secret id=signalwire_token,src=./freeswitch/signalwire_token.txt \
#     -t zenith-freeswitch:audiostream ./freeswitch
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates gnupg2 wget lsb-release \
        cmake libssl-dev zlib1g-dev libevent-dev libspeexdsp-dev \
        build-essential git autoconf automake libtool pkg-config \
        libwebsockets-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala libfreeswitch-dev a partir dos .deb vendorizados (sem tocar em
# repositório externo). Fallback: se vendor/debs/ estiver vazio (ex: upgrade
# de versão do FreeSWITCH), descomente o bloco de repositório SignalWire
# abaixo para baixar uma versão atualizada.
COPY vendor/debs/*.deb /tmp/debs/
RUN apt-get install -y --no-install-recommends /tmp/debs/*.deb \
    && rm -rf /tmp/debs /var/lib/apt/lists/*

# --- Fallback via repositório SignalWire (descomentar se vendor/debs/ não
#     tiver a versão necessária do FreeSWITCH) ---
# RUN --mount=type=secret,id=signalwire_token \
#     TOKEN="$(cat /run/secrets/signalwire_token)" \
#     && wget --http-user=signalwire --http-password="$TOKEN" \
#         -O /usr/share/keyrings/signalwire-freeswitch-repo.gpg \
#         https://freeswitch.signalwire.com/repo/deb/debian-release/signalwire-freeswitch-repo.gpg \
#     && echo "machine freeswitch.signalwire.com login signalwire password $TOKEN" > /etc/apt/auth.conf.d/signalwire.conf \
#     && chmod 600 /etc/apt/auth.conf.d/signalwire.conf \
#     && echo "deb [signed-by=/usr/share/keyrings/signalwire-freeswitch-repo.gpg] https://freeswitch.signalwire.com/repo/deb/debian-release/ $(lsb_release -sc) main" \
#         > /etc/apt/sources.list.d/freeswitch.list \
#     && apt-get update && apt-get install -y --no-install-recommends libfreeswitch-dev \
#     && rm -rf /var/lib/apt/lists/*

RUN git clone --recurse-submodules https://github.com/amigniter/mod_audio_stream.git /usr/src/mod_audio_stream

WORKDIR /usr/src/mod_audio_stream
RUN mkdir build && cd build && cmake -DCMAKE_BUILD_TYPE=Release .. && make

FROM safarov/freeswitch:1.10.12

# libspeexdsp e libssl/libz já existem na imagem base; libevent não existe e
# precisa ser copiado do stage de build (mesma base Debian bookworm).
COPY --from=builder /usr/lib/x86_64-linux-gnu/libevent-2.1.so.7* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libevent_core-2.1.so.7* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libevent_pthreads-2.1.so.7* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libevent_openssl-2.1.so.7* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libevent_extra-2.1.so.7* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/src/mod_audio_stream/build/mod_audio_stream.so /usr/lib/freeswitch/mod/mod_audio_stream.so
