# NTP Server (UDP/123) – Docker & Swarm Guide

---

## Project layout

```
.
├── Dockerfile
├── ntp_server.py       # UDP NTP responder (port 123)
└── healthcheck.py      # Container health probe (simple NTP round‑trip)
```

---

## Versioning strategy

Use immutable, human‑readable tags like `V1.8`, `V2.4`, etc. Align Docker tags with Git tags to keep code and images in sync:

```bash
# Create a Git tag and push it
git tag -a V2.4 -m "NTP server V2.4"
git push origin V2.4
```

> Tip: Prefer **upper‑case V** for visibility (e.g., `V2.4`). Avoid reusing tags.

---

## Build the image

### Local build

```bash
# Build with a version tag
docker build -t ntp-server:V2.4 .

# (Optional) also tag a moving alias, e.g., latest
docker tag ntp-server:V2.4 ntp-server:latest
```

### Multi‑arch build (optional)

```bash
# One‑time setup
docker buildx create --use --name ntp-bx || docker buildx use ntp-bx

# Build and push multi‑arch (amd64 + arm64)
# Replace REGISTRY/USER with yours (e.g., ghcr.io/you or registry.example.com/you)
REG=REGISTRY/USER
VER=V2.4

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t $REG/ntp-server:$VER \
  -t $REG/ntp-server:latest \
  --push .
```

---

## Push to a registry (if you have one)

```bash
# Example: Docker Hub
docker tag ntp-server:V2.4 USER/ntp-server:V2.4
docker push USER/ntp-server:V2.4
```

If you don’t use a registry, you can **load the image on each node** (e.g., `docker save`/`docker load`) before deploying the Swarm stack.

---

## Run locally (quick test)

```bash
docker run --rm \
  --cap-add NET_BIND_SERVICE \
  -p 123:123/udp \
  -v /etc/localtime:/etc/localtime:ro \
  --name ntp-test ntp-server:V2.4

# In another shell, you should see logs like:
# Local socket:  ('0.0.0.0', 123)
# Received 1 packets
# Sent to 127.0.0.1:5xxxx
```

> **Why `NET_BIND_SERVICE`?** Binding to ports <1024 requires extra capability in containers.

---

## Swarm stack deployment

Create a stack file (e.g., `stack.yml`) like below. This mirrors your snippet and adds a few best‑practices comments.

```yaml
yaml
version: "3.9"

networks:
  your-network:      # define your network here
    external: true   # or define it here if you don’t have it yet

services:
  ntp-server:
    image: ntp-server:V1.8   # ⬅️ pin a specific version tag
    networks:
      - sina-network

    # Publish directly on the node (no mesh/NAT) to preserve client IPs
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
      mode: global           # one task per node (recommended for NTP)
      update_config:
        delay: 4s            # short stagger for rolling updates
      resources:
        limits:
          cpus: "1"
          memory: 1G
    logging:
      options:
        max-file: "3"
        max-size: 100m
```

Deploy/update the stack:

```bash
# Create or update
docker stack deploy -c stack.yml ntp

# Check rollout
docker service ls
docker service ps ntp_ntp-server

# Logs (per container)
docker service logs -f ntp_ntp-server
```

> **Host mode note:** `mode: host` publishes UDP/123 **on each node’s host network**. Ensure firewalls allow inbound UDP/123 and nothing else on the host is already binding that port.

---

## Upgrading to a new version

1. **Build & push** a new tag, e.g., `V2.4`.
2. **Edit `stack.yml`** to `image: ntp-server:V2.4` (do not reuse old tags).
3. **Redeploy** the stack: `docker stack deploy -c stack.yml ntp`.
4. Verify tasks update sequentially (thanks to `update_config.delay`).

Rollback is just changing the tag back and redeploying.

---

## Healthcheck (optional inline)

If you prefer a Dockerfile‑level healthcheck, add something like this to your Dockerfile (the repo already includes `healthcheck.py`):

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python3 /healthcheck.py || exit 1
```

In Swarm, health status influences task replacement.

---

## Troubleshooting

* **Port already in use:** Another service may be listening on UDP/123. Check with `ss -ulpn | grep :123` on each node.
* **Firewall:** Allow inbound UDP/123 (and ensure Swarm node‑to‑node ports are open if needed).
* **No responses:**

  * Confirm container is healthy and bound to `0.0.0.0:123` in logs.
  * Test locally from the node: `ntpdate -q 127.0.0.1` or `chronyc -a sourcestats` (if available).
  * Ensure `mode: host` is in effect (mesh mode can mangle UDP sources).
* **Time accuracy:** This server is a simple responder. For production‑grade timekeeping, sync the host with upstream NTP (e.g., `chrony`) and/or extend the code for disciplined time sources.

---

## Security & ops notes

* Run in **global** mode so every node serves NTP for its local network.
* Keep images **small** and updated. Rebuild on base image updates.
* Consider running on dedicated hosts or tainted nodes to avoid port conflicts.
* Limit capabilities to the minimum (here, just `NET_BIND_SERVICE`).

---
