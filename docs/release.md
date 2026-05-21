# Release

Release tags use `vMAJOR.MINOR.PATCH`, for example:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The GitHub release workflow builds and pushes the Docker image to Docker Hub, then uploads:

- `compose.yaml`
- `env.example`

The generated `env.example` is release-specific and fills in the Docker image and tag for that release.

## Docker Image Tags

For `v0.1.0`, the workflow publishes:

- `n120318/aethera:0.1.0`
- `n120318/aethera:0.1`
- `n120318/aethera:latest`

## Required GitHub Actions Secrets

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

`DOCKERHUB_TOKEN` should be a Docker Hub access token with permission to push `n120318/aethera`.

