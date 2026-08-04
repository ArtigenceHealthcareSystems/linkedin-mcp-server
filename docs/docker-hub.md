# Docker publishing note

This fork is configured for independent `uvx` and `.mcpb` releases.

It does **not** publish an official Docker image as part of its default release workflow.

For the supported install path, use:

```bash
uvx artigence-linkedin-mcp@latest
```

If you decide to publish your own image for this fork later, keep the HTTP example bound to loopback so the unauthenticated MCP endpoint stays on the local machine:

```bash
docker run -it --rm \
  -v ~/.linkedin-mcp:/home/pwuser/.linkedin-mcp \
  -p 127.0.0.1:8080:8080 \
  your-registry/linkedin-mcp-server:latest \
  --transport streamable-http --host 0.0.0.0 --port 8080 --path /mcp
```

`--host 0.0.0.0` is required inside the container so the published port can reach the server. The `127.0.0.1:` prefix on `-p` is what keeps the endpoint off your network. Without that prefix, Docker publishes on every interface.

Docker still cannot run `--login` because containers do not provide a display server. Create the browser profile on the host first with:

```bash
uvx artigence-linkedin-mcp@latest --login
```

If you later add a Docker publishing workflow, update this note with your real registry, image name, and any fork-specific setup steps.
