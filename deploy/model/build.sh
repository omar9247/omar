#!/usr/bin/env sh
# Build the model image. Trains the git-ignored artifacts/ first if they are missing (25 s, seed 0),
# so a fresh clone can go straight to a runnable image.
#   deploy/model/build.sh [tag]
set -eu
cd "$(dirname "$0")/../.."
tag="${1:-aura-bio/model:local}"

if ! docker info >/dev/null 2>&1; then
  echo "docker is not reachable: start Docker, add your user to the docker group, or run this with sudo" >&2
  exit 1
fi

if [ ! -f artifacts/model_2d.pt ] || [ ! -f artifacts/ewma.json ]; then
  echo "artifacts/ missing: training seed 0 (no evaluation)"
  uv run python -m model.train --seeds 1 --no-eval
fi

docker build -f deploy/model/Dockerfile -t "$tag" .
echo "built $tag"
echo "run:  docker run --rm -p 8001:8001 --read-only --tmpfs /tmp $tag"
