#!/usr/bin/env bash
# Run a one-off command on AWS in its own short-lived task, like `docker compose run --rm` does locally.
# Same image, settings and secrets as the api, inside the vpc, so it can reach the database.
#
#   infra/task.sh                                                migrations (alembic upgrade head)
#   infra/task.sh python harvest_scripts/seed.py                 load nba_data.json
#   infra/task.sh python harvest_scripts/make_admin.py <email>   grant admin
#
# Waits for it to finish, prints its output, and exits with its exit code.
set -euo pipefail
export MSYS_NO_PATHCONV=1 # git bash on windows would rewrite /ecs/... into a windows path
cd "$(dirname "$0")"

CLUSTER=$(terraform output -raw cluster)
REGION=$(terraform output -raw region)
NETWORK=$(terraform output -raw run_task_network)
LOG_GROUP="/ecs/$CLUSTER/migrate"

if [ $# -gt 0 ]; then
  # the arguments as a json list, replacing the migrate container's command for this run only
  args=$(printf '"%s",' "$@")
  OVERRIDES="{\"containerOverrides\":[{\"name\":\"migrate\",\"command\":[${args%,}]}]}"
  echo "==> running on aws: $*"
else
  OVERRIDES='{}'
  echo "==> running on aws: alembic upgrade head"
fi

TASK=$(aws ecs run-task \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --task-definition "$CLUSTER-migrate" \
  --launch-type FARGATE \
  --network-configuration "$NETWORK" \
  --overrides "$OVERRIDES" \
  --query 'tasks[0].taskArn' --output text)
TASK_ID=${TASK##*/}

echo "    task $TASK_ID started, waiting for it to finish (usually under a minute)"
aws ecs wait tasks-stopped --region "$REGION" --cluster "$CLUSTER" --tasks "$TASK"

# its output: the awslogs driver names each stream <prefix>/<container>/<task id>
aws logs tail "$LOG_GROUP" --region "$REGION" --since 30m \
  --log-stream-name-prefix "migrate/migrate/$TASK_ID" --format short || true

CODE=$(aws ecs describe-tasks --region "$REGION" --cluster "$CLUSTER" --tasks "$TASK" \
  --query 'tasks[0].containers[0].exitCode' --output text)
if [ "$CODE" != "0" ]; then
  # no exit code means it never started (image missing, secret unreadable...); the reason says why
  REASON=$(aws ecs describe-tasks --region "$REGION" --cluster "$CLUSTER" --tasks "$TASK" \
    --query 'tasks[0].stoppedReason' --output text)
  echo "==> failed (exit code $CODE): $REASON"
  exit 1
fi
echo "==> done"
