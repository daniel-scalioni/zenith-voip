# syntax=docker/dockerfile:1
#
# Build mod_audio_fork (drachtio-freeswitch-modules) fora da árvore contra os
# headers do FreeSWITCH 1.10.x e copia o .so compilado para a imagem vanilla
# já usada pelo projeto (safarov/freeswitch:1.10.12), preservando conf/dialplan
# existentes.
#
# Plano B se este build falhar: trocar a imagem final por uma que já empacote
# os módulos drachtio prontos (ex.: linha drachtio/drachtio-freeswitch-mrf) —
# exige revalidar todo freeswitch/conf, por isso não é o caminho principal.

# Repositório APT da SignalWire exige uma conta + token pessoal desde a
# migração do repo público (o antigo login de convidado não existe mais).
# A URL antiga de cadastro (id.signalwire.com/signup/account/new) está morta.
# O token válido é um "Personal Access Token" (prefixo pat_), gerado no painel
# da SignalWire — não confundir com o Project Token (PT...)/SignIn Key (PSK_...)
# do Space, que são para as APIs de voz/vídeo, não para este repositório.
# Passe via build secret (não fica gravado em nenhuma layer da imagem):
#   docker compose -f docker-compose.app.yml build \
#     --secret id=signalwire_token,src=./freeswitch/signalwire_token.txt \
#     freeswitch
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates gnupg2 wget lsb-release \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=secret,id=signalwire_token \
    TOKEN="$(cat /run/secrets/signalwire_token)" \
    && wget --http-user=signalwire --http-password="$TOKEN" \
        -O /usr/share/keyrings/signalwire-freeswitch-repo.gpg \
        https://freeswitch.signalwire.com/repo/deb/debian-release/signalwire-freeswitch-repo.gpg \
    && echo "machine freeswitch.signalwire.com login signalwire password $TOKEN" > /etc/apt/auth.conf.d/signalwire.conf \
    && chmod 600 /etc/apt/auth.conf.d/signalwire.conf \
    && echo "deb [signed-by=/usr/share/keyrings/signalwire-freeswitch-repo.gpg] https://freeswitch.signalwire.com/repo/deb/debian-release/ $(lsb_release -sc) main" \
        > /etc/apt/sources.list.d/freeswitch.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        libfreeswitch-dev \
        build-essential git autoconf automake libtool pkg-config \
        libwebsockets-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/drachtio/drachtio-freeswitch-modules.git /usr/src/drachtio-freeswitch-modules

WORKDIR /usr/src/drachtio-freeswitch-modules/modules/mod_audio_fork
RUN make && make install

# Path a confirmar no primeiro build real: mod_audio_fork.so deve cair em
# /usr/lib/freeswitch/mod/ (layout padrão Debian) via "make install" acima.
# Se o build falhar por path, ajustar aqui antes de seguir para o stage final.

FROM safarov/freeswitch:1.10.12

COPY --from=builder /usr/lib/freeswitch/mod/mod_audio_fork.so /usr/lib/freeswitch/mod/mod_audio_fork.so
