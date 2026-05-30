locals {
  create_project     = var.project_id == ""
  create_environment = var.environment_id == "" && !local.create_project
  create_service     = var.service_id == ""

  project_id = local.create_project ? railway_project.this[0].id : var.project_id

  environment_id = var.environment_id != "" ? var.environment_id : (
    local.create_project ?
    railway_project.this[0].default_environment.id :
    railway_environment.this[0].id
  )

  service_id = local.create_service ? railway_service.this[0].id : var.service_id

  custom_domain_enabled = trimspace(var.custom_domain) != ""
}

resource "railway_project" "this" {
  count = local.create_project ? 1 : 0

  name         = var.project_name
  description  = var.project_description
  private      = var.project_private
  workspace_id = trimspace(var.workspace_id) != "" ? var.workspace_id : null

  default_environment = {
    name = var.environment_name
  }
}

resource "railway_environment" "this" {
  count = local.create_environment ? 1 : 0

  name       = var.environment_name
  project_id = local.project_id
}

resource "railway_service" "this" {
  count = local.create_service ? 1 : 0

  name       = var.service_name
  project_id = local.project_id

  source_repo        = trimspace(var.source_repo) != "" ? var.source_repo : null
  source_repo_branch = trimspace(var.source_repo_branch) != "" ? var.source_repo_branch : null
  root_directory     = trimspace(var.root_directory) != "" ? var.root_directory : null
}

resource "railway_custom_domain" "app" {
  count = local.custom_domain_enabled ? 1 : 0

  domain         = var.custom_domain
  environment_id = local.environment_id
  service_id     = local.service_id
}

# Non-sensitive Zoomify backend configuration.
resource "railway_variable" "config" {
  for_each = toset(var.config_env_var_names)

  name           = each.key
  value          = var.env_vars[each.key]
  environment_id = local.environment_id
  service_id     = local.service_id
}

# Secrets — values are sensitive; for_each uses explicit key names only.
resource "railway_variable" "secret" {
  for_each = toset(var.secret_env_var_names)

  name           = each.key
  value          = var.secret_env_vars[each.key]
  environment_id = local.environment_id
  service_id     = local.service_id
}
