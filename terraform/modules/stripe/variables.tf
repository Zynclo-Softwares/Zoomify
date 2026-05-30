variable "environment" {
  type        = string
  description = "Environment label embedded in Stripe metadata (dev, prod)."
}

variable "webhook_url" {
  type        = string
  description = "Public URL Stripe sends subscription lifecycle events to."
}

variable "app_name" {
  type        = string
  default     = "zoomify"
  description = "Prefix for Stripe lookup keys and product names."
}

variable "starter_monthly_usd" {
  type        = number
  default     = 10
  description = "Starter plan monthly price in USD."
}

variable "pro_monthly_usd" {
  type        = number
  default     = 25
  description = "Pro plan monthly price in USD."
}

variable "yearly_discount_percent" {
  type        = number
  default     = 15
  description = "Percent discount applied to annual billing (matches app plans.py)."
}

variable "create_webhook_endpoint" {
  type        = bool
  default     = true
  description = "Create a Stripe webhook endpoint. Disable for local dev (use Stripe CLI instead)."
}

variable "stripe_api_key" {
  type        = string
  sensitive   = true
  description = "Stripe secret API key for payment-link script (from secrets.auto.tfvars)."
}
