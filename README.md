---

NTP Server (UDP/123) – Docker & Swarm Ready

A lightweight Python-based NTP responder packaged for Docker and Swarm.
It can run standalone (docker run) or globally across a Swarm cluster with proper healthchecks and logging.


---

Project Layout

.
├── Dockerfile        # Container build definition
├── ntp_server.py     # UDP NTP server (listens on port 123/udp)
└── healthcheck.py    # Health probe (performs a local NTP round-trip)


---

Features

Minimal NTP responder (suitable for lab/testing use).

Container healthcheck via healthcheck.py.

Supports Docker Swarm global mode (one task per node).

Logs handled via Python’s logging module (no stdout spam).

Ignores local healthcheck IPs by default:

127.0.0.1

::1

Docker gateway IP (172.17.0.1)


> These can be customized inside the Dockerfile for your environment.





---


Build the Image

Local Build

docker build -t ntp-server:V2.4 .


---

Run Locally (Quick Test)

docker run --rm \
  --cap-add NET_BIND_SERVICE \
  -p 123:123/udp \
  -v /etc/localtime:/etc/localtime:ro \
  --name ntp-test ntp-server:V2.4

Logs will show activity like:

[INFO] Listening on ('0.0.0.0', 123)
[INFO] Handled NTP request from 192.168.204.50


---

Swarm Deployment

stack.yml example:

version: "3.9"

services:
  ntp-server:
    image: USER/ntp-server:V2.4   # pin a version
    ports:
      - target: 123
        published: 123
        protocol: udp
        mode: host
    cap_add:
      - NET_BIND_SERVICE
    volumes:
      - /etc/localtime:/etc/localtime:ro
    deploy:
      mode: global
      update_config:
        delay: 4s
      resources:
        limits:
          cpus: "1"
          memory: 1G
    logging:
      options:
        max-file: "3"
        max-size: 100m

Deploy it:

docker stack deploy -c stack.yml ntp
docker service logs -f ntp_ntp-server


---

Healthcheck

Add this snippet in Dockerfile to enable container health monitoring:

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python3 /healthcheck.py || exit 1


---

Troubleshooting

Port already in use: ss -ulpn | grep :123

Firewall issues: allow inbound UDP/123.

Testing from host:
ntpdate -q 127.0.0.1
or
chronyc -a sourcestats

No response in Swarm: ensure mode: host is used (not ingress mesh).



---

Notes

This project is not a disciplined NTP server — it just echoes time.

Run in Swarm global mode for consistency across nodes.



---

