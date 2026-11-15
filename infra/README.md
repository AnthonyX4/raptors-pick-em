# Deploying to AWS (ECS)

The backend on AWS, defined in this folder with Terraform. It's the same shape as `docker-compose.yml`:

| Compose | AWS | File |
|---|---|---|
| `db` + `raptors-pgdata` volume | RDS Postgres 17 in private subnets | `database.tf` |
| `migrate` (runs, exits) | a one-off ECS task, run by `deploy.sh` before each rollout | `ecs.tf`, `task.sh` |
| `api` + `ports: 8000:8000` | ECS service behind an Application Load Balancer (health check `GET /`) | `ecs.tf`, `loadbalancer.tf` |
| `poller` | ECS service, exactly one task, never two during a deploy | `ecs.tf` |
| `docker compose build` | image pushed to ECR, tagged with the git commit | `registry.tf`, `deploy.sh` |
| `env_file: Backend/.env` | Secrets Manager (passwords) + task environment (the rest) | `secrets.tf`, `ecs.tf` |
| S3 keys in `.env` | an IAM task role, no keys anywhere | `iam.tf` |
| Compose network | a VPC: public subnets (load balancer, tasks), private subnets (database) | `network.tf` |
| `docker compose logs` | CloudWatch Logs, kept 14 days | `ecs.tf` |

All commands run in **Git Bash** from this `infra/` folder (the scripts are bash).

## First time (about 30 minutes, most of it waiting for the database)

**1. Install the AWS CLI and Terraform.** In PowerShell:

```
winget install Amazon.AWSCLI
winget install Hashicorp.Terraform
```

Close and reopen Git Bash, then check: `aws --version` and `terraform version`.

**2. Give Terraform an AWS login.** Terraform creates networks, roles and databases, so it needs broad permissions. Not your root login: an IAM user made for it.

- IAM → Users → **Create user** `terraform-admin` (no console access) → Attach policies directly → **AdministratorAccess** → Create.
- The user → Security credentials → **Create access key** → *Command Line Interface (CLI)* → copy both keys.
- In Git Bash: `aws configure` → paste the two keys, region `us-east-2`, output `json`. They're saved in `~/.aws/credentials`, outside the repo.
- Check: `aws sts get-caller-identity` shows `user/terraform-admin`.

**3. Your values.** `cp terraform.tfvars.example terraform.tfvars`, then fill in the bucket, your email (for budget warnings) and the Mailtrap username and password from `Backend/.env`. `terraform.tfvars` is gitignored.

**4. Create the foundation, without the load balancer and services yet** (there's no image to run until step 5):

```
terraform init
terraform apply -var running=false
```

Read the plan (about 38 resources to add, nothing to change or destroy), type `yes`. The database takes 5–10 minutes.

**5. Deploy:**

```
./deploy.sh
```

It builds the image, pushes it to ECR, runs the migrations on AWS, then shows a second plan that adds the load balancer and both services (type `yes`), and waits until they're healthy. It ends with your address: `http://raptors-pick-em-<numbers>.us-east-2.elb.amazonaws.com/docs`.

**6. Load the season and make yourself admin:**

```
./task.sh python harvest_scripts/seed.py
```

Register on the new address's `/docs`, then:

```
./task.sh python harvest_scripts/make_admin.py you@example.com
```

## Day to day

| To | Run |
|---|---|
| Ship new code (commit first) | `./deploy.sh` |
| Run a one-off command on AWS | `./task.sh <command...>` |
| Follow the poller's log | `MSYS_NO_PATHCONV=1 aws logs tail /ecs/raptors-pick-em/poller --follow` |
| Follow the api's log | `MSYS_NO_PATHCONV=1 aws logs tail /ecs/raptors-pick-em/api --follow` |
| Switch off between demos (keeps the data) | `./pause.sh` |
| Switch back on (new address) | `./resume.sh` |
| Delete everything, data included | `terraform destroy` |

`MSYS_NO_PATHCONV=1` stops Git Bash rewriting `/ecs/...` into a Windows path; the scripts set it themselves.

## What it costs

Roughly, in us-east-2, running all month (credits pay for it on the Free plan):

| Piece | ≈ / month |
|---|---|
| Load balancer | $16–20 |
| API and poller tasks (0.25 vCPU, 0.5 GB each) | $18 |
| RDS `db.t4g.micro` + 20 GB | $14 |
| Public IPv4 addresses (load balancer ×2, tasks ×2) | $14 |
| ECR, Secrets Manager, CloudWatch | $1–3 |
| **Running** | **≈ $60–70** |
| **Paused** (database stopped, storage only) | **≈ $3–5** |

So pause it when you're not showing it. The budget alert (`budget.tf`) emails you when the month is on track to pass `monthly_budget_usd` ($30 by default), counted before credits so the warning comes while there are credits left. AWS restarts a stopped database after 7 days on its own; `./pause.sh` again stops it again.

## Design choices

- **No NAT gateway.** The usual setup hides tasks in private subnets behind a NAT gateway (≈ $33/month by itself). Here they sit in public subnets with public IPs, for their outbound traffic only: the `app` security group accepts nothing but port 8000 from the load balancer. The database is in private subnets with no route in or out.
- **The poller never doubles.** Its service stops the old task before starting the new one (`deployment_maximum_percent = 100`, minimum 0). The api does the opposite: new task first, healthy, then the old one goes, so it's never down during a deploy.
- **Failed deploys undo themselves.** The circuit breaker rolls a service back to its last working version if new tasks keep failing.
- **Migrations run before the rollout**, as their own task, never inside the api (two api tasks starting together would race).
- **The image is the commit.** Each deploy is tagged with the git commit (`-dirty-<time>` if `Backend/` has uncommitted changes), and `image.auto.tfvars` remembers it so a plain `terraform apply` never rolls back by accident. ECR keeps the last 10.
- **State is local** (`terraform.tfstate`, gitignored, holds the generated passwords). One person, one machine; a team would keep it in S3.
- **`terraform destroy` deletes the database without a snapshot.** It's a demo; `pause.sh` is the everyday off switch.

## When something's wrong

- **A deploy hangs at "waiting for ... stable":** `aws ecs describe-services --cluster raptors-pick-em --services api --query 'services[0].events[0:5]'` says why (image not found, health check failing, can't read the secret). Then check the api log above.
- **The address times out:** a fresh load balancer takes a couple of minutes to resolve.
- **AWS refuses to create something with a message about your account plan:** some services are limited on the Free plan; tell me which one.
