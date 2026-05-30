locals {
  environment = "dev"
  app_name    = "zoomify"

  webhook_url = "http://127.0.0.1:8000/api/billing/webhook"

  stripe_api_key = (
    trimspace(var.stripe_api_key) != "" ?
    trimspace(var.stripe_api_key) :
    trimspace(try(var.secret_env_vars["STRIPE_SECRET_KEY"], ""))
  )
}
