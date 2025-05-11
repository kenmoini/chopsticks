
FROM registry.fedoraproject.org/fedora:42

USER 0

WORKDIR /opt/app-root/src
COPY ./src /opt/app-root/src

RUN dnf update -y \
 && dnf install -y python3 python3-pip python3-requests python3-libvirt libvirt openssl \
 && dnf clean all \
 && rm -rf /var/cache/yum \
 && mkdir -p /opt/app-root/src \
 && pip3 install -r /opt/app-root/src/requirements.txt \
 && chmod a+x /opt/app-root/src/start.sh

ENV FLASK_RUN_PORT=3434
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASH_TLS_CERT=
ENV FLASH_TLS_KEY=

USER 1001

EXPOSE 3434

CMD ["/opt/app-root/src/start.sh"]
