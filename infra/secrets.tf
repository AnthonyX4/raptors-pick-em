# Secrets Manager: what Backend/.env holds on your machine. ECS reads each key when a task starts and hands
# it to the container as an environment variable, so config.py reads it exactly as it reads .env.
# One secret with several keys rather than one secret each: secrets manager bills per secret.

resource "random_password" "secret_key" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "app" {
  name = "${var.name}/app"

  # delete at once on terraform destroy, instead of the default 7-30 day recovery window,
  # so destroying and recreating doesn't collide with a secret still pending deletion
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id

  secret_string = jsonencode({
    SECRET_KEY    = random_password.secret_key.result
    DATABASE_URL  = "postgresql+asyncpg://${aws_db_instance.main.username}:${random_password.db.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}"
    MAIL_USERNAME = var.mail_username
    MAIL_PASSWORD = var.mail_password
  })
}

locals {
  # the keys above, in the shape a task definition's "secrets" list wants: "<secret arn>:<json key>::"
  app_secrets = [
    for key in ["SECRET_KEY", "DATABASE_URL", "MAIL_USERNAME", "MAIL_PASSWORD"] : {
      name      = key
      valueFrom = "${aws_secretsmanager_secret.app.arn}:${key}::"
    }
  ]
}
