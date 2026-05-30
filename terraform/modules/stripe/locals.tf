locals {
  prefix = "${var.app_name}-${var.environment}"

  starter_yearly_usd = floor(
    var.starter_monthly_usd * 12 * (100 - var.yearly_discount_percent) / 100 + 0.5
  )
  pro_yearly_usd = floor(
    var.pro_monthly_usd * 12 * (100 - var.yearly_discount_percent) / 100 + 0.5
  )

  common_metadata = {
    app         = var.app_name
    environment = var.environment
  }

  webhook_events = [
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
  ]
}
