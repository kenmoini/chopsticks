
FROM registry.fedoraproject.org/fedora:42

ENV FLASK_RUN_PORT=3434
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASH_TLS_CERT=
ENV FLASH_TLS_KEY=

EXPOSE 3434

USER 0

WORKDIR /opt/app-root/src
COPY ./src /opt/app-root/src

RUN dnf update -y \
 && dnf install -y python3 python3-pip python3-requests python3-libvirt libvirt-client openssl \
 && dnf clean all \
 && rm -rf /var/cache/yum

# None of the user stuff really matters lol
RUN mkdir -p /opt/app-root/src \
 && pip3 install -r /opt/app-root/src/requirements.txt \
 && chmod a+x /opt/app-root/src/start.sh \
 && useradd -u 1001 -M -d /opt/app-root chopsticks
 #&& usermod -aG libvirt chopsticks \
 #&& usermod -aG qemu chopsticks \
 #&& usermod -aG kvm chopsticks

USER 1001

CMD ["/opt/app-root/src/start.sh"]
