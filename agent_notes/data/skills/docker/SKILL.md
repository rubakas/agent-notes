---
name: docker
group: domain
description: "Docker development: Dockerfiles, Compose, multi-stage builds, and service patterns. Context7-style: loads only the relevant reference on demand."
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

Based on the user's current task, use the Read tool to load the relevant reference file from this skill's directory. Only load the file(s) you need — do not load all of them.

| Topic | File | Use when |
|---|---|---|
| Dockerfile | dockerfile.md | Writing or editing Dockerfiles, multi-stage builds, layer optimization, language-specific patterns |
| Compose | compose.md | Writing docker-compose.yml, service definitions, health checks, dev/prod configs |

The reference files are in the same directory as this skill file. After reading, apply the patterns and conventions to the user's code.
