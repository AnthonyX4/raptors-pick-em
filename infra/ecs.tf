# ECS: compose's job on aws. A task definition is a compose service block (image, command, env, sizes);
# a service keeps N copies of one running and replaces any that stop. All on Fargate: aws runs the
# containers, there's no server to manage.

resource "aws_ecs_cluster" "main" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "disabled" # extra per-task metrics, billed; cloudwatch logs are enough here
  }
}

# what docker compose logs shows, kept 14 days (the default is forever, and storage adds up)
resource "aws_cloudwatch_log_group" "task" {
  for_each = toset(["api", "poller", "migrate"])

  name              = "/ecs/${var.name}/${each.key}"
  retention_in_days = 14
}

locals {
  image = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"

  # Backend/.env minus the secrets. S3 has no keys: the task role is the credential
  app_environment = [
    { name = "S3_BUCKET_NAME", value = var.profile_pics_bucket },
    { name = "S3_REGION", value = var.region },
    { name = "MAIL_SERVER", value = var.mail_server },
    { name = "MAIL_PORT", value = tostring(var.mail_port) },
    { name = "MAIL_FROM", value = var.mail_from },
    { name = "MAIL_USE_TLS", value = "true" },
    { name = "FRONTEND_URL", value = var.frontend_url },
  ]

  # what every container shares, like compose's x-app anchor: same image, settings and secrets
  container_common = {
    image       = local.image
    essential   = true
    environment = local.app_environment
    secrets     = local.app_secrets
  }

  # one container definition per program, each already json: the three differ in shape (only the api has
  # a port, only the api keeps the image's CMD), and json strings keep terraform from having to reconcile that
  container_definitions = {
    api = jsonencode([merge(local.container_common, {
      name             = "api" # no command: the image's CMD, fastapi run on $PORT
      portMappings     = [{ containerPort = 8000, protocol = "tcp" }]
      stopTimeout      = 30
      logConfiguration = local.log_config["api"]
    })])
    poller = jsonencode([merge(local.container_common, {
      name             = "poller"
      command          = ["python", "poller.py"]
      stopTimeout      = 60 # SIGTERM lets the tick in progress finish (compose's stop_grace_period)
      logConfiguration = local.log_config["poller"]
    })])
    migrate = jsonencode([merge(local.container_common, {
      name             = "migrate"
      command          = ["alembic", "upgrade", "head"] # task.sh overrides it to seed or make an admin
      stopTimeout      = 30
      logConfiguration = local.log_config["migrate"]
    })])
  }

  log_config = {
    for program in ["api", "poller", "migrate"] : program => {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.task[program].name
        awslogs-region        = var.region
        awslogs-stream-prefix = program
      }
    }
  }
}

resource "aws_ecs_task_definition" "app" {
  for_each = local.container_definitions

  family                   = "${var.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc" # each task gets its own network interface and private ip
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions    = each.value

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64" # what docker build produces on your pc
  }
}

resource "aws_ecs_service" "api" {
  count = var.running ? 1 : 0

  name            = "api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app["api"].arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true # for its own outbound traffic; inbound is only the load balancer (security group)
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api[0].arn
    container_name   = "api"
    container_port   = 8000
  }

  # a new version must pass the load balancer's health check within a minute of starting
  health_check_grace_period_seconds = 60

  # rolling deploy: start the new task, wait until it's healthy, then stop the old one (never fewer than
  # desired_count serving). if new tasks keep failing, stop and go back to the last version that worked
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.http] # the target group must be attached to a load balancer first
}

resource "aws_ecs_service" "poller" {
  count = var.running ? 1 : 0

  name            = "poller"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app["poller"].arn
  desired_count   = 1 # exactly one, always: two pollers would both send reminders and score games
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  # the opposite of the api's rollout: stop the old poller before starting the new one, so a deploy can
  # never have two running at once. a minute without a poller costs nothing, two of them could double-send
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}
