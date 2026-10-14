---
name: docker
group: domain
description: "Dockerfiles and Compose reference: multi-stage builds, health checks, services. Use when writing/debugging Dockerfiles, docker-compose files, or containerizing apps."
triggers:
  - docker
  - Dockerfile
  - docker-compose
  - container
  - multi-stage build
  - health check
  - Docker Compose
---

# Docker Reference

Based on the user's current task, read the relevant reference file(s) from this skill's directory. Only load what you need.

## Dockerfile guidance

- [dockerfile-base-and-structure.md](dockerfile-base-and-structure.md) — Read when: choosing a base image or structuring a Dockerfile
- [dockerfile-multistage-and-layers.md](dockerfile-multistage-and-layers.md) — Read when: using multi-stage builds or optimizing layers
- [dockerfile-security.md](dockerfile-security.md) — Read when: securing a Dockerfile or adding health checks, or rebuilding and testing images
- [dockerfile-patterns.md](dockerfile-patterns.md) — Read when: writing language-specific Dockerfiles or using build arguments

## Docker Compose guidance

- [compose-configuration.md](compose-configuration.md) — Read when: configuring basic Compose files, health checks, or environment variables
- [compose-services.md](compose-services.md) — Read when: setting up Node.js, Rails, or Python/Django services
- [compose-infrastructure.md](compose-infrastructure.md) — Read when: configuring databases, caches, reverse proxies, or message queues
- [compose-examples.md](compose-examples.md) — Read when: seeing complete examples, dev/prod configs, or best practices

After reading, apply the patterns and conventions to your code.
