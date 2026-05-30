module "stripe" {
  source = "../../modules/stripe"

  environment    = local.environment
  app_name       = local.app_name
  webhook_url    = local.webhook_url
  stripe_api_key = local.stripe_api_key
}

locals {
  route53_record_names = var.enable_railway && var.manage_app_dns ? [var.app_domain] : []

  route53_record_targets = var.enable_railway && var.manage_app_dns ? {
    (var.app_domain) = module.railway[0].app_dns_record.target
  } : {}
}

module "railway" {
  source = "../../modules/railway"
  count  = var.enable_railway ? 1 : 0

  project_name       = var.railway_project_name
  service_name       = var.railway_service_name
  environment_name   = var.railway_environment_name
  workspace_id       = var.railway_workspace_id
  source_repo        = var.railway_source_repo
  source_repo_branch = var.railway_source_repo_branch
  project_id         = var.railway_project_id
  environment_id     = var.railway_environment_id
  service_id         = var.railway_service_id
  custom_domain      = var.app_domain

  config_env_var_names = local.backend_config_env_names
  env_vars             = local.railway_env_vars

  secret_env_var_names = local.backend_secret_env_names
  secret_env_vars      = local.railway_secret_env_vars
}

data "aws_route53_zone" "app" {
  count = var.enable_railway && var.manage_app_dns ? 1 : 0

  name         = var.route53_zone_name
  private_zone = false
}

module "route53" {
  source = "../../modules/route53"
  count  = var.enable_railway && var.manage_app_dns ? 1 : 0

  zone_id        = data.aws_route53_zone.app[0].zone_id
  record_names   = local.route53_record_names
  record_targets = local.route53_record_targets

  depends_on = [module.railway]
}
