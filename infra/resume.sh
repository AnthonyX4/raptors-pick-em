#!/usr/bin/env bash
# Bring a paused deployment back: start the database, recreate the load balancer and services.
# The api comes back at a new address (a new load balancer gets a new name), printed at the end.
#
#   infra/resume.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")"

REGION=$(terraform output -raw region)
DB=$(terraform output -raw database)
CLUSTER=$(terraform output -raw cluster)

STATUS=$(aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$DB" \
  --query 'DBInstances[0].DBInstanceStatus' --output text)
if [ "$STATUS" = "stopped" ]; then
  echo "==> starting the database (a few minutes)"
  aws rds start-db-instance --region "$REGION" --db-instance-identifier "$DB" --output text --query 'DBInstance.DBInstanceStatus'
fi
aws rds wait db-instance-available --region "$REGION" --db-instance-identifier "$DB"

echo "running = true" > running.auto.tfvars
echo "==> recreating the load balancer and services (read the plan, then type yes)"
terraform apply

echo "==> waiting for the api and poller to be stable"
aws ecs wait services-stable --region "$REGION" --cluster "$CLUSTER" --services api poller
echo
echo "Running: $(terraform output -raw api_url)/docs"
