variable "project_name" {
  type        = string
  default     = "zoomify"
  description = "Railway project name when creating a new project."
}

variable "project_description" {
  type        = string
  default     = "Zoomify production backend"
  description = "Railway project description when creating a new project."
}

variable "project_private" {
  type        = bool
  default     = true
  description = "Whether the Railway project is private."
}

variable "workspace_id" {
  type        = string
  default     = ""
  description = "Railway workspace ID. Required when your token has access to multiple workspaces."
}

variable "environment_name" {
  type        = string
  default     = "production"
  description = "Railway environment name (default env on new projects)."
}

variable "service_name" {
  type        = string
  default     = "zoomify"
  description = "Railway service name when creating a new service."
}

variable "source_repo" {
  type        = string
  default     = ""
  description = "Optional GitHub repo (owner/name) to connect on service create."
}

variable "source_repo_branch" {
  type        = string
  default     = ""
  description = "Branch for source_repo (required when source_repo is set)."
}

variable "root_directory" {
  type        = string
  default     = ""
  description = "Optional monorepo subdirectory for the Railway service."
}

variable "custom_domain" {
  type        = string
  default     = ""
  description = "Public app hostname (e.g. zoomify.zynclo.com). Creates railway_custom_domain when set."
}

variable "project_id" {
  type        = string
  default     = ""
  description = "Existing Railway project ID. Leave empty to create a new project."
}

variable "environment_id" {
  type        = string
  default     = ""
  description = "Existing Railway environment ID. Leave empty to use/create the default environment."
}

variable "service_id" {
  type        = string
  default     = ""
  description = "Existing Railway service ID. Leave empty to create a new service."
}

variable "env_vars" {
  type        = map(string)
  default     = {}
  description = "Non-sensitive service variables (Stripe links, Clerk JWKS URL, rate limits, etc.)."
}

variable "config_env_var_names" {
  type        = list(string)
  default     = []
  description = "Static env var names for for_each (required when values are unknown until apply)."
}

variable "secret_env_vars" {
  type        = map(string)
  default     = {}
  sensitive   = true
  description = "Sensitive service variables (BYOK key, MongoDB URI, Stripe secret key)."
}

variable "secret_env_var_names" {
  type        = list(string)
  default     = ["BYOK_PRIVATE_KEY", "MONGODB_URI", "STRIPE_SECRET_KEY"]
  description = "Names of secret_env_vars to sync (non-sensitive keys for for_each)."
}
