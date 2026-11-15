# The Application Load Balancer: the public front door. It gets a permanent address
# (<name>-<number>.us-east-2.elb.amazonaws.com), listens on port 80, and forwards each request to a
# healthy api task's private ip on port 8000. It is the most expensive piece per hour that can't be
# paused, so running = false removes it (and its address changes when it comes back).

resource "aws_lb" "api" {
  count = var.running ? 1 : 0

  name               = var.name
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

# the set of api tasks the load balancer may send to. ecs adds and removes tasks here as they start and stop
resource "aws_lb_target_group" "api" {
  count = var.running ? 1 : 0

  name        = "${var.name}-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip" # fargate tasks have their own ip each, there's no server to point at
  vpc_id      = aws_vpc.main.id

  # GET / is the cheap endpoint built for exactly this: no database, so a database blip doesn't make
  # every task look broken at once and get replaced (GET /health is for deploys, it runs a query)
  health_check {
    path                = "/"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30 # let in-flight requests finish when a task is replaced, but don't wait the default 5 minutes
}

resource "aws_lb_listener" "http" {
  count = var.running ? 1 : 0

  load_balancer_arn = aws_lb.api[0].arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api[0].arn
  }
}
