variable "webhook_url" {
  type        = string
  default     = "https://api.zoomify.zynclo.com/api/billing/webhook"
  description = "Public Stripe webhook URL for production."
}

variable "enable_railway" {
  type        = bool
  default     = false
  description = "Create/manage Railway project + service and sync env vars. Requires RAILWAY_TOKEN in the shell environment."
}

variable "railway_project_name" {
  type        = string
  default     = "zoomify"
  description = "Railway project name when Terraform creates the project."
}

variable "railway_service_name" {
  type        = string
  default     = "zoomify"
  description = "Railway service name when Terraform creates the service."
}

variable "railway_environment_name" {
  type        = string
  default     = "production"
  description = "Railway environment name (default env on new projects)."
}

variable "railway_workspace_id" {
  type        = string
  default     = ""
  description = "Railway workspace ID. Set only if your token has access to multiple workspaces."
}

variable "railway_source_repo" {
  type        = string
  default     = ""
  description = "Optional GitHub repo (owner/name) to connect when creating the Railway service."
}

variable "railway_source_repo_branch" {
  type        = string
  default     = "main"
  description = "Branch for railway_source_repo."
}

variable "railway_project_id" {
  type        = string
  default     = ""
  description = "Existing Railway project ID. Leave empty to let Terraform create the project."
}

variable "railway_environment_id" {
  type        = string
  default     = ""
  description = "Existing Railway environment ID. Leave empty to use/create the default environment."
}

variable "railway_service_id" {
  type        = string
  default     = ""
  description = "Existing Railway service ID. Leave empty to let Terraform create the service."
}

variable "app_domain" {
  type        = string
  default     = "zoomify.zynclo.com"
  description = "Public app hostname. Railway custom domain + Route 53 CNAME when manage_app_dns = true."
}

variable "manage_app_dns" {
  type        = bool
  default     = true
  description = "Create Route 53 CNAME(s) pointing app_domain at Railway (requires AWS credentials)."
}

variable "route53_zone_name" {
  type        = string
  default     = "zynclo.com"
  description = "Route 53 hosted zone for app_domain (parent zone of zoomify.zynclo.com)."
}

variable "clerk_publishable_key" {
  type        = string
  default     = ""
  description = "Clerk publishable key for VITE_CLERK_PUBLISHABLE_KEY (public; baked into Docker frontend build)."
}

variable "railway_env_vars" {
  type        = map(string)
  default     = {}
  description = "Non-secret backend env vars (Clerk JWKS, rate limits). Stripe links are merged from the stripe module."
}

variable "stripe_api_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Stripe secret for Terraform apply. Optional if STRIPE_SECRET_KEY is set in secret_env_vars."
}

variable "secret_env_vars" {
  type        = map(string)
  default     = {}
  sensitive   = true
  description = "Sensitive backend env vars. Copy secrets.auto.tfvars.example → secrets.auto.tfvars (gitignored)."
}
