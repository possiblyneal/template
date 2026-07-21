# Container files

Podman-first container deployment templates. GitHub Actions and local scripts can build from `Containerfile`; server deployment can use Quadlet files in `quadlet/`.

## Quadlet conventions

These templates mirror common deployed Quadlet patterns from the homelab:

- `[Unit]` waits for `network-online.target`.
- `[Container]` sets `ContainerName`, `Image`, optional `AutoUpdate`, `Network`, `NetworkAlias`, `PublishPort`, volumes, env, and health checks.
- `[Service]` uses `Restart=always`, `RestartSec=10s`, and explicit start/stop timeouts.
- `[Install]` targets `default.target` for rootless user services. Use `multi-user.target` only for system services.
- Rootless services commonly use `/home/neal/.config/...`, `/home/neal/.local/share/...`, and `/home/neal/.config/containers/env/...`.
- Use `UserNS=keep-id` when the container should map the host user into the container.
- Use `:Z` on bind mounts when SELinux relabeling is needed.

## Template variables

Replace these placeholders before deploy:

- `{{PROJECT_NAME}}`
- `{{DESCRIPTION}}`
- `{{IMAGE}}`
- `{{HOST_PORT}}`
- `{{CONTAINER_PORT}}`
- `{{CONTAINER_COMMAND}}`
- `{{HEALTHCHECK_COMMAND}}`

## Rootless install path

Copy Quadlet files to:

```text
~/.config/containers/systemd/
```

Then reload and start with systemd user services.
