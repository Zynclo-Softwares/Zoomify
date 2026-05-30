module "stripe" {
  source = "../../modules/stripe"

  environment             = local.environment
  app_name                = local.app_name
  webhook_url             = local.webhook_url
  create_webhook_endpoint = false
  stripe_api_key          = local.stripe_api_key
}
