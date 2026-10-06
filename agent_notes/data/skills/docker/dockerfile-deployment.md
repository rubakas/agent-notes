# Best Practices and Deployment

## Contents

- [Best Practices Summary](#best-practices-summary)
- [CI/CD Integration](#cicd-integration)
- [Testing Dockerfiles](#testing-dockerfiles)

---

## Best Practices Summary

### DO

1. **Use specific versions** - `FROM node:20.11.0-alpine`, never `:latest`
2. **Use multi-stage builds** - Reduces attack surface, smaller images
3. **Run as non-root user** - UID > 10,000 for security
4. **Order layers by change frequency** - Better caching
5. **Use .dockerignore** - Essential for security and size
6. **Combine apt-get update with install** - Prevents cache issues
7. **Use `set -o pipefail`** - Catch errors in piped commands
8. **Add HEALTHCHECK** - Production-necessary for orchestration
9. **Scan for vulnerabilities** - Use Docker Scout or Trivy
10. **Pin to digests for critical apps** - Supply chain security

### DON'T

1. **Use :latest tag** - Unpredictable, unreproducible builds
2. **Run as root** - Security risk, use UID > 10,000
3. **Store secrets in image** - Use runtime environment variables
4. **Install unnecessary packages** - Increases attack surface
5. **Use ADD when COPY works** - ADD has unexpected behaviors
6. **Forget .dockerignore** - 87% of images have vulnerabilities
7. **Skip HEALTHCHECK** - Orchestration cannot detect failures
8. **Separate apt-get update from install** - Cache inconsistency risk

---

## CI/CD Integration

Rebuild images frequently with `--no-cache` to obtain security patches. Integrate automated building and testing through GitHub Actions or equivalent pipelines.

```bash
# Build without cache for security updates
docker build --no-cache -t my-app:latest .

# Scan in CI pipeline
docker scout cves my-app:latest --exit-code
```

---

## Testing Dockerfiles

```bash
# Build
docker build -t my-app:latest .

# Run
docker run -p 3000:3000 my-app:latest

# Check size
docker images my-app:latest

# Scan for vulnerabilities
docker scout cves my-app:latest
trivy image my-app:latest

# Inspect layers
docker history my-app:latest

# Test as non-root (should work)
docker run --user 10001:10001 my-app:latest

# Test read-only filesystem
docker run --read-only --tmpfs /tmp my-app:latest
```

---

## References and Sources

This guide is based on official Docker documentation:

- [Docker Best Practices Official Documentation](https://docs.docker.com/build/building/best-practices/)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker USER Instruction Best Practices](https://www.docker.com/blog/understanding-the-docker-user-instruction/)
- [Docker HEALTHCHECK Reference](https://docs.docker.com/reference/dockerfile/#healthcheck)
- [Dockerfile Reference](https://docs.docker.com/reference/dockerfile/)
- [Docker Security Documentation](https://docs.docker.com/engine/security/)

Last updated: December 2025
