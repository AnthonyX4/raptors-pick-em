# Postgres 17 on RDS: compose's db service, with aws doing the disk, backups and patches.
# Private subnets, no public address, and only the app's security group may connect.

resource "random_password" "db" {
  length  = 32
  special = false # it goes inside DATABASE_URL, where @ : / would need escaping
}

resource "aws_db_subnet_group" "main" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = "17" # the major version, as in docker-compose.yml; rds picks the minor
  instance_class = var.db_instance_class

  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = "raptors"
  username = "raptors"
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = false # a standby copy in a second zone would double the price

  backup_retention_period    = 1    # a day of point-in-time backups
  auto_minor_version_upgrade = true # security patches inside 17.x
  apply_immediately          = true

  # terraform destroy deletes the database for good, no final snapshot: this is a demo deployment and
  # pause.sh (not destroy) is how it's switched off between uses. flip both before holding real users' data
  skip_final_snapshot = true
  deletion_protection = false
}
