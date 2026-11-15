# Raptors Pick'em on AWS: the same four pieces as docker-compose.yml, as Terraform.
#   compose db       -> rds postgres (database.tf), in private subnets
#   compose migrate  -> a one-off ecs task (ecs.tf, run by deploy.sh before each rollout)
#   compose api      -> an ecs service behind a load balancer (ecs.tf, loadbalancer.tf)
#   compose poller   -> an ecs service that never runs two copies (ecs.tf)
# README.md in this folder has the commands.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # state stays in this folder (terraform.tfstate, gitignored: it holds the generated passwords).
  # fine for one person; a team would move it to an s3 bucket so everyone shares one copy
}

provider "aws" {
  region = var.region

  # every resource gets these, so the billing console can show this project's costs on their own
  default_tags {
    tags = {
      Project   = var.name
      ManagedBy = "terraform"
    }
  }
}
