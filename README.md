# NTP Server (UDP/123) – Docker & Swarm Ready

A lightweight Python-based NTP responder packaged for Docker and Swarm.  
It can run standalone (docker run), via **Docker Compose** on a single host, or globally across a **Swarm** cluster with proper healthchecks and logging.

> ⚠️ This is **not** a disciplined/production-grade NTP daemon; it’s intended for labs/testing where you just need a simple time responder.

---

## Project Layout

```
.
├── Dockerfile        # Container build definition
├── ntp_server.py     # UDP NTP server (listens on port 123/udp)
└── healthcheck.py    # Health probe (performs a local NTP round-trip)
```

---

## Features

- Minimal NTP responder (suitable for lab/testing use).
- Container healthcheck via `healthcheck.py`.
- Supports Docker Swarm **global** mode (one task per node).
- Logs handled via Python’s logging module (no stdout spam).
- Ignores local healthcheck IPs by default:
  - `127.0.0.1`
  - `::1`
  - Docker gateway IP (`172.17.0.1`)

> These can be customized inside the Dockerfile for your environment.

---

## Build the Image

Local build (replace `tag` with your version, e.g., `2.8`):

```bash
git clone https://github.com/mhosamsh/ntp-server.git
cd ntp-server

docker build -t ntp-server:tag .
```

---

## Run Locally (Quick Test)

```bash
docker run --rm   --cap-add NET_BIND_SERVICE   -p 123:123/udp   -v /etc/localtime:/etc/localtime:ro   --name ntp-test ntp-server:tag
```

Expected logs:

```
[INFO] Listening on ('0.0.0.0', 123)
[INFO] Handled NTP request from 192.168.204.50
```

---

## Docker Compose (single host)

Single-host mode is great for a lab box. You have two options:

### Option A — Host networking (preserves host’s native UDP/123)
> Use this if you want the container to bind directly to the host’s UDP/123. You **cannot** use `ports:` with host mode.

`docker-compose.yml`:
```yaml
version: "3.9"

services:
  ntp-server:
    image: ntp-server:tag
    container_name: ntp-server
    network_mode: host
    cap_add:
      - NET_BIND_SERVICE
    volumes:
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python3", "/healthcheck.py"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
    logging:
      driver: json-file
      options:
        max-size: 100m
        max-file: "3"
```

Bring it up:
```bash
docker compose up -d
```

### Option B — Bridge networking (simple; NATed client IPs)
> Use this if you prefer standard Docker port publishing and don’t need true client IP preservation.

`docker-compose.yml`:
```yaml
version: "3.9"

services:
  ntp-server:
    image: ntp-server:tag
    container_name: ntp-server
    ports:
      - "123:123/udp"
    cap_add:
      - NET_BIND_SERVICE
    volumes:
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python3", "/healthcheck.py"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
    logging:
      driver: json-file
      options:
        max-size: 100m
        max-file: "3"
```

Bring it up:
```bash
docker compose up -d
```

---

## Docker Swarm (global on every node; preserves client IPs)

For multi-node deployments, Swarm with **host-mode** publishing keeps client IPs intact and runs one replica per node.

Create `stack-ntp.yml`:
```yaml
version: "3.9"

networks:
  ntp-network:

services:
  ntp-server:
    image: ntp-server:tag

    networks:
      - ntp-network

    # Publish directly on the node (no mesh/NAT), keeps client IP
    ports:
      - target: 123
        published: 123
        protocol: udp
        mode: host

    cap_add:
      - NET_BIND_SERVICE

    volumes:
      - /etc/localtime:/etc/localtime:ro

    restart: always

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
```

Deploy it:
```bash
docker swarm init   # skip if your swarm is already initialized
docker stack deploy -c stack-ntp.yml ntp
docker service logs -f ntp_ntp-server
```

---

## Healthcheck (Dockerfile snippet)

If not already present, add this in your `Dockerfile` to enable container health monitoring:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3   CMD python3 /healthcheck.py || exit 1
```

---

## Troubleshooting

- **Port already in use**  
  ```bash
  ss -ulpn | grep :123
  ```
- **Firewall issues**  
  Allow inbound **UDP/123** to the host (and between nodes if using Swarm).
- **Testing from host**  
  ```bash
  ntpdate -q 127.0.0.1
  # or
  chronyc -a sourcestats
  ```
- **No response in Swarm**  
  Ensure `mode: host` is used (not ingress mesh).

---

## Notes

- Prefer **Swarm + host-mode** if you need correct, un-NATed client IPs.
- Single-host Compose is simpler but NATs client IPs (unless using `network_mode: host`).
- This project is meant for **lab/testing**, not precision timekeeping.

---
