# ECR: aws's private image registry. deploy.sh builds Backend/Dockerfile on your machine and pushes the
# image here, tagged with the git commit, and the task definitions point at that tag.

resource "aws_ecr_repository" "app" {
  name                 = var.name
  image_tag_mutability = "MUTABLE"
  force_delete         = true # let terraform destroy remove the repository even with images in it

  image_scanning_configuration {
    scan_on_push = true # a free check of the image's packages against known vulnerabilities
  }
}

# storage is billed per GB, and every deploy adds a ~150 MB image: keep the last 10, enough to roll back
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the 10 most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
