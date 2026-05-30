variable "stripe_api_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Stripe test secret for Terraform apply. Set in secrets.auto.tfvars (auto-loaded)."
}

variable "secret_env_vars" {
  type        = map(string)
  default     = {}
  sensitive   = true
  description = "Optional. STRIPE_SECRET_KEY here is used if stripe_api_key is unset."
}
