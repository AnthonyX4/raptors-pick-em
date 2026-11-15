#!/usr/bin/env bash
# Ship the current code to AWS, in the order compose starts things:
#   1. build Backend/ into an image tagged with the git commit, push it to ECR
#   2. point the task definitions at that image
#   3. run the migrations as a one-off task (compose's migrate service); stop here if they fail
#   4. terraform apply: the services roll onto the new version (you approve the plan)
#   5. wait until ecs reports both services stable, print the address
#
#   infra/deploy.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1 # git bash on windows would rewrite /ecs/... into a windows path
cd "$(dirname "$0")"

if grep -qs 'running *= *false' running.auto.tfvars; then
  echo "The deployment is paused. Run infra/resume.sh first."
  exit 1
fi

REGION=$(terraform output -raw region)
REPO=$(terraform output -raw ecr_repository_url)
CLUSTER=$(terraform output -raw cluster)

# the commit is the version. uncommitted changes in Backend/ get a unique tag of their own, so the image
# for a commit is always exactly that commit
TAG=$(git rev-parse --short HEAD)
if ! git diff --quiet HEAD -- ../Backend || [ -n "$(git ls-files --others --exclude-standard ../Backend)" ]; then
  TAG="$TAG-dirty-$(date +%s)"
  echo "(Backend/ has uncommitted changes, deploying them as $TAG)"
fi

echo "==> 1/5 building and pushing $REPO:$TAG"
docker build -t "$REPO:$TAG" ../Backend
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${REPO%%/*}"
docker push "$REPO:$TAG"

# remembered for every later terraform apply, so a plain apply never rolls back to an older image
echo "image_tag = \"$TAG\"" > image.auto.tfvars

echo "==> 2/5 task definitions -> $TAG"
terraform apply -auto-approve -target=aws_ecs_task_definition.app

echo "==> 3/5 migrations"
./task.sh

echo "==> 4/5 rolling the services (read the plan, then type yes)"
terraform apply

echo "==> 5/5 waiting for the api and poller to be stable"
aws ecs wait services-stable --region "$REGION" --cluster "$CLUSTER" --services api poller

URL=$(terraform output -raw api_url)
echo
echo "Deployed $TAG: $URL/docs"
