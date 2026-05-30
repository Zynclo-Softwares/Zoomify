locals {
  environment = "prod"
  app_name    = "zoomify"

  webhook_url = var.webhook_url

  stripe_api_key = (
    trimspace(var.stripe_api_key) != "" ?
    trimspace(var.stripe_api_key) :
    trimspace(try(var.secret_env_vars["STRIPE_SECRET_KEY"], ""))
  )

  stripe_env_vars = {
    for key, value in module.stripe.env_vars : key => value
    if value != null && trimspace(tostring(value)) != ""
  }

  # Non-secret backend keys — keep in sync with root .env.example.
  backend_config_env_names = [
    "AUTO_CREATE_INDEXES_ON_BOOT",
    "CLERK_JWKS_URL",
    "MONGODB_DATABASE",
    "OPENROUTER_BASE_URL",
    "RATE_LIMIT_FREE_PER_MINUTE",
    "RATE_LIMIT_STARTER_PER_MINUTE",
    "RATE_LIMIT_PRO_PER_MINUTE",
    "STRIPE_LINK_STARTER_MONTHLY",
    "STRIPE_LINK_STARTER_YEARLY",
    "STRIPE_LINK_PRO_MONTHLY",
    "STRIPE_LINK_PRO_YEARLY",
    "STRIPE_WEBHOOK_SECRET",
    "VITE_CLERK_PUBLISHABLE_KEY",
  ]

  # Secret backend keys — keep in sync with root .env.example.
  backend_secret_env_names = [
    "BYOK_PRIVATE_KEY",
    "MONGODB_URI",
    "STRIPE_SECRET_KEY",
  ]

  backend_config_env_defaults = {
    AUTO_CREATE_INDEXES_ON_BOOT = "false"
    OPENROUTER_BASE_URL         = "https://openrouter.ai/api/v1"
  }

  railway_env_vars = merge(
    local.backend_config_env_defaults,
    local.stripe_env_vars,
    var.railway_env_vars,
    trimspace(var.clerk_publishable_key) != "" ? {
      VITE_CLERK_PUBLISHABLE_KEY = trimspace(var.clerk_publishable_key)
    } : {},
  )

  railway_secret_env_vars = merge(var.secret_env_vars, {
    STRIPE_SECRET_KEY = local.stripe_api_key
  })

  backend_env_var_names = sort(concat(
    local.backend_config_env_names,
    local.backend_secret_env_names,
  ))
}
