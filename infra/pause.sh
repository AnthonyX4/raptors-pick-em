#!/usr/bin/env bash
# Switch the deployment off between demos, keeping all the data:
#   - removes the load balancer and both services (the parts billed by the hour)
#   - stops the database (only its storage is billed while stopped)
# What's left costs a few dollars a month: database storage, images in ECR, the secret.
# AWS starts a stopped database again by itself after 7 days; run this again to stop it again.
#
#   infra/pause.sh      and later      infra/resume.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")"

REGION=$(terraform output -raw region)
DB=$(terraform output -raw database)

echo "running = false" > running.auto.tfvars
echo "==> removing the load balancer and services (read the plan, then type yes)"
terraform apply

STATUS=$(aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$DB" \
  --query 'DBInstances[0].DBInstanceStatus' --output text)
if [ "$STATUS" = "available" ]; then
  echo "==> stopping the database"
  aws rds stop-db-instance --region "$REGION" --db-instance-identifier "$DB" --output text --query 'DBInstance.DBInstanceStatus'
else
  echo "==> the database is '$STATUS', leaving it"
fi
echo "Paused."
