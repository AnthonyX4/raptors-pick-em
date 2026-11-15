output "api_url" {
  description = "The API's public address. Open <api_url>/docs."
  value       = var.running ? "http://${aws_lb.api[0].dns_name}" : "paused (resume.sh brings it back, at a new address)"
}

output "region" {
  value = var.region
}

output "ecr_repository_url" {
  description = "Where deploy.sh pushes the image."
  value       = aws_ecr_repository.app.repository_url
}

output "cluster" {
  value = aws_ecs_cluster.main.name
}

output "database" {
  description = "The RDS instance's id, for aws rds stop-db-instance / start-db-instance."
  value       = aws_db_instance.main.identifier
}

# what aws ecs run-task needs to start a one-off task (migrations, seeding) in the right subnets with
# the right security group, already in the shape its --network-configuration flag takes
output "run_task_network" {
  value = "awsvpcConfiguration={subnets=[${join(",", aws_subnet.public[*].id)}],securityGroups=[${aws_security_group.app.id}],assignPublicIp=ENABLED}"
}
