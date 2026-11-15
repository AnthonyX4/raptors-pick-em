# Two roles, because two different things act for a task:
#   execution role: ECS itself, before the container starts. pulls the image, reads the secrets,
#                   creates the log stream. the app never holds these permissions
#   task role:      the app inside the container. boto3 finds its temporary credentials automatically
#                   (S3_ACCESS_KEY_ID is unset), so no access keys exist anywhere on aws

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

# aws's standard policy for this job: pull from ecr, write to cloudwatch logs
resource "aws_iam_role_policy_attachment" "execution_standard" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.app.arn] # this one secret, nothing else in the account
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "read-app-secret"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

# the same permissions as the raptors-pick-em-dev iam user: upload and delete under profile_pics/, nothing else
data "aws_iam_policy_document" "task_profile_pics" {
  statement {
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${var.profile_pics_bucket}/profile_pics/*"]
  }
}

resource "aws_iam_role_policy" "task_profile_pics" {
  name   = "manage-profile-pics"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_profile_pics.json
}
