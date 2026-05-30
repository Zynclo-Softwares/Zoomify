output "environment" {
  value = module.stripe.environment
}

output "product_ids" {
  value = module.stripe.product_ids
}

output "price_ids" {
  value = module.stripe.price_ids
}

output "payment_link_urls" {
  value = module.stripe.payment_link_urls
}

output "webhook_endpoint_id" {
  value = module.stripe.webhook_endpoint_id
}

output "webhook_secret" {
  value     = module.stripe.webhook_secret
  sensitive = true
}

output "env_vars" {
  description = "Copy into production .env (also set STRIPE_SECRET_KEY to your live secret key)."
  value       = module.stripe.env_vars
  sensitive   = true
}

output "env_file_content" {
  description = "Paste into production .env after terraform apply."
  value       = module.stripe.env_file_content
  sensitive   = true
}

output "railway_synced_variable_names" {
  description = "Env var names pushed to Railway when enable_railway = true."
  value       = try(module.railway[0].synced_variable_names, [])
}

output "backend_env_var_names" {
  description = "Canonical backend env var names (matches root .env.example + Docker build key)."
  value       = local.backend_env_var_names
}

output "backend_config_env_names" {
  description = "Non-secret backend env vars synced to Railway."
  value       = local.backend_config_env_names
}

output "backend_secret_env_names" {
  description = "Secret backend env vars synced to Railway."
  value       = local.backend_secret_env_names
}

output "railway_project_id" {
  description = "Railway project ID (created or imported)."
  value       = try(module.railway[0].project_id, null)
}

output "railway_environment_id" {
  description = "Railway environment ID."
  value       = try(module.railway[0].environment_id, null)
}

output "railway_service_id" {
  description = "Railway service ID."
  value       = try(module.railway[0].service_id, null)
}

output "railway_dashboard_url" {
  description = "Railway project dashboard URL."
  value       = try(module.railway[0].dashboard_url, null)
}

output "app_domain" {
  description = "Public Zoomify app hostname on Railway."
  value       = try(module.railway[0].app_domain, null)
}

output "app_dns_records" {
  description = "Route 53 CNAME record names synced for the app domain."
  value       = try(module.route53[0].record_names, [])
}

output "railway_sync_summary" {
  description = "Counts of Railway variables synced (when enabled)."
  value = var.enable_railway ? {
    config = module.railway[0].synced_config_count
    secret = module.railway[0].synced_secret_count
  } : null
}
