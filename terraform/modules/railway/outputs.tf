output "project_id" {
  description = "Railway project ID."
  value       = local.project_id
}

output "environment_id" {
  description = "Railway environment ID."
  value       = local.environment_id
}

output "service_id" {
  description = "Railway service ID."
  value       = local.service_id
}

output "created_project" {
  description = "True when Terraform created the Railway project."
  value       = local.create_project
}

output "created_service" {
  description = "True when Terraform created the Railway service."
  value       = local.create_service
}

output "dashboard_url" {
  description = "Railway project dashboard URL."
  value       = "https://railway.com/project/${local.project_id}"
}

output "app_domain" {
  description = "Custom app domain attached to the Railway service."
  value       = local.custom_domain_enabled ? var.custom_domain : null
}

output "app_dns_record" {
  description = "Route 53 CNAME for the app domain (name -> Railway target)."
  value = local.custom_domain_enabled ? {
    name   = var.custom_domain
    target = railway_custom_domain.app[0].dns_record_value
  } : null
}

output "app_dns_verification_record" {
  description = "Optional Route 53 CNAME for Railway domain verification."
  value = local.custom_domain_enabled && trimspace(railway_custom_domain.app[0].verification_host_label) != "" ? {
    name   = "${railway_custom_domain.app[0].verification_host_label}.${railway_custom_domain.app[0].zone}"
    target = railway_custom_domain.app[0].verification_record_value
  } : null
}

output "synced_variable_names" {
  description = "Env var names pushed to Railway (values omitted)."
  value       = sort(concat(var.config_env_var_names, var.secret_env_var_names))
}

output "synced_config_count" {
  description = "Number of non-secret variables synced."
  value       = length(var.config_env_var_names)
}

output "synced_secret_count" {
  description = "Number of secret variables synced."
  value       = length(var.secret_env_var_names)
}
