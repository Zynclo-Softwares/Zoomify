# Zoomify Stripe infrastructure (Terraform)

Manages Stripe **products**, **prices**, **Payment Links**, and the **billing webhook** for Zoomify pricing.

## Layout

```
terraform/
  modules/stripe/          # Stripe products, prices, payment links, webhook
  modules/railway/         # Create Railway project/service + custom domain + env vars
  modules/route53/         # Route 53 CNAME records (app -> Railway)
  environments/dev/        # Test mode (sk_test_...)
  environments/prod/       # Live mode (sk_live_...) + optional Railway sync
```

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- Python 3 with the `stripe` package (`uv sync` from repo root)
- **Secrets file:** copy `secrets.auto.tfvars.example` → `secrets.auto.tfvars` in each environment (gitignored, auto-loaded on apply)
- **Prod Railway:** `RAILWAY_TOKEN` in your shell (Railway → Account Settings → Tokens)
- **Prod DNS:** AWS CLI credentials with Route 53 access on `zynclo.com` (for `manage_app_dns`)

## Dev apply

```bash
cd terraform/environments/dev
cp secrets.auto.tfvars.example secrets.auto.tfvars   # set stripe_api_key = sk_test_...
terraform init
terraform apply
terraform output -json env_vars
```

After apply, copy outputs into the root `.env`:

```bash
terraform output -raw env_file_content >> ../../../.env
# Also set STRIPE_SECRET_KEY to the same Stripe secret key used in secrets.auto.tfvars
```

## Prod apply

Use a **live** key and update URLs in `prod/locals.tf` or `terraform.tfvars` first.

```bash
cd terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
cp secrets.auto.tfvars.example secrets.auto.tfvars
# Edit both files, then set enable_railway = true
export RAILWAY_TOKEN="..."   # only when enable_railway = true (or already in ~/.zshrc)
terraform init
terraform apply
```

Stripe key stays in `secrets.auto.tfvars` (`STRIPE_SECRET_KEY`). Railway auth uses shell `RAILWAY_TOKEN`.

**Greenfield Railway:** leave `railway_project_id`, `railway_environment_id`, and `railway_service_id` empty. Terraform creates the project, default environment, service, **custom domain** (`app_domain`), and **Route 53 CNAME** in `route53_zone_name`.

**Existing Railway:** set those three IDs in `terraform.tfvars` to adopt resources created outside Terraform.

### Prod env files (Terraform convention)

| File | Gitignored | Purpose |
|------|------------|---------|
| `terraform.tfvars` | yes | Railway names, optional repo, Clerk JWKS, rate limits |
| `secrets.auto.tfvars` | yes | Auto-loaded: `secret_env_vars` (`BYOK_PRIVATE_KEY`, `GITHUB_TOKEN`, `MONGODB_URI`, `STRIPE_SECRET_KEY`) |

`STRIPE_SECRET_KEY` in `secrets.auto.tfvars` is used for **both** Terraform Stripe apply and the Railway app runtime. Set it once.

The **railway module** merges:

1. Runtime defaults (`AUTO_CREATE_INDEXES_ON_BOOT`)
2. **Stripe module outputs** (payment links + webhook secret)
3. `railway_env_vars` from `terraform.tfvars`
4. `secret_env_vars` from `secrets.auto.tfvars`

Set `enable_railway = false` to manage Stripe only (no Railway API calls).

```bash
./export-railway-env.sh   # list synced variable names after apply
```

## Outputs

| Output | Maps to `.env` |
|--------|----------------|
| `payment_link_urls.starter_monthly` | `STRIPE_LINK_STARTER_MONTHLY` |
| `payment_link_urls.starter_yearly` | `STRIPE_LINK_STARTER_YEARLY` |
| `payment_link_urls.pro_monthly` | `STRIPE_LINK_PRO_MONTHLY` |
| `payment_link_urls.pro_yearly` | `STRIPE_LINK_PRO_YEARLY` |
| `webhook_secret` | `STRIPE_WEBHOOK_SECRET` |

`STRIPE_SECRET_KEY` is **not** created by Terraform — set it manually to your Stripe secret API key.

## Local webhooks

Stripe cannot reach `http://127.0.0.1:8000` directly. For local webhook testing use the [Stripe CLI](https://stripe.com/docs/stripe-cli):

```bash
stripe listen --forward-to localhost:8000/api/billing/webhook
```

Use the CLI signing secret as `STRIPE_WEBHOOK_SECRET` during local dev, or point `webhook_url` at an ngrok tunnel.
