variable "region" {
  description = "AWS region for everything. us-east-2 (Ohio) is where the profile picture bucket lives."
  type        = string
  default     = "us-east-2"
}

variable "name" {
  description = "Prefix for every resource name."
  type        = string
  default     = "raptors-pick-em"
}

# --- switches deploy.sh, pause.sh and resume.sh set through *.auto.tfvars files ---

variable "running" {
  description = "false removes the load balancer and both services (the parts that cost money by the hour), keeping the database, images and secrets. pause.sh / resume.sh flip it."
  type        = bool
  default     = true
}

variable "image_tag" {
  description = "Which image in ECR the tasks run. deploy.sh sets it to the git commit it pushed."
  type        = string
  default     = "latest"
}

# --- sizes, the smallest fargate and rds allow ---

variable "api_desired_count" {
  description = "How many API tasks run behind the load balancer."
  type        = number
  default     = 1
}

variable "task_cpu" {
  description = "CPU units per task (256 = a quarter of a vCPU, the smallest Fargate size)."
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "Memory per task in MiB (512 is the most 256 CPU units allow at the bottom tier)."
  type        = number
  default     = 512
}

variable "db_instance_class" {
  description = "RDS size. db.t4g.micro is the smallest, and free-tier eligible."
  type        = string
  default     = "db.t4g.micro"
}

# --- the app's settings (see Backend/config.py) ---

variable "profile_pics_bucket" {
  description = "The existing S3 bucket for profile pictures, created by hand in the console. Terraform only grants the tasks access to it."
  type        = string
}

variable "frontend_url" {
  description = "Where the React app lives; password reset and reminder emails link there."
  type        = string
  default     = "http://localhost:5173"
}

variable "mail_server" {
  type    = string
  default = "sandbox.smtp.mailtrap.io"
}

variable "mail_port" {
  type    = number
  default = 587
}

variable "mail_username" {
  type      = string
  sensitive = true
}

variable "mail_password" {
  type      = string
  sensitive = true
}

variable "mail_from" {
  type    = string
  default = "noreply@example.com"
}

# --- cost guard ---

variable "budget_email" {
  description = "Where AWS emails a warning when this month's spending is on track to pass monthly_budget_usd."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly spending, before credits, that triggers the warning emails."
  type        = number
  default     = 30
}
