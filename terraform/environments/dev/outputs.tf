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
  description = "Copy into root .env (also set STRIPE_SECRET_KEY to the same API key used for apply)."
  value       = module.stripe.env_vars
  sensitive   = true
}

output "env_file_content" {
  description = "Paste into .env after terraform apply."
  value       = module.stripe.env_file_content
  sensitive   = true
}
