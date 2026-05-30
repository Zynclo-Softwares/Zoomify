resource "stripe_product" "starter" {
  name        = "${title(var.app_name)} Starter (${var.environment})"
  description = "500 extractions/day on the Zoomify platform layer (BYOK)."
  metadata = merge(local.common_metadata, {
    plan = "starter"
  })
}

resource "stripe_product" "pro" {
  name        = "${title(var.app_name)} Pro (${var.environment})"
  description = "Unlimited extractions with fair-use rate limits (BYOK)."
  metadata = merge(local.common_metadata, {
    plan = "pro"
  })
}

resource "stripe_price" "starter_monthly" {
  product     = stripe_product.starter.id
  currency    = "usd"
  unit_amount = var.starter_monthly_usd * 100
  lookup_key  = "${local.prefix}-starter-monthly"
  nickname    = "Zoomify Starter monthly"

  recurring {
    interval = "month"
  }

  metadata = merge(local.common_metadata, {
    plan     = "starter"
    interval = "monthly"
  })
}

resource "stripe_price" "starter_yearly" {
  product     = stripe_product.starter.id
  currency    = "usd"
  unit_amount = local.starter_yearly_usd * 100
  lookup_key  = "${local.prefix}-starter-yearly"
  nickname    = "Zoomify Starter yearly"

  recurring {
    interval = "year"
  }

  metadata = merge(local.common_metadata, {
    plan     = "starter"
    interval = "yearly"
  })
}

resource "stripe_price" "pro_monthly" {
  product     = stripe_product.pro.id
  currency    = "usd"
  unit_amount = var.pro_monthly_usd * 100
  lookup_key  = "${local.prefix}-pro-monthly"
  nickname    = "Zoomify Pro monthly"

  recurring {
    interval = "month"
  }

  metadata = merge(local.common_metadata, {
    plan     = "pro"
    interval = "monthly"
  })
}

resource "stripe_price" "pro_yearly" {
  product     = stripe_product.pro.id
  currency    = "usd"
  unit_amount = local.pro_yearly_usd * 100
  lookup_key  = "${local.prefix}-pro-yearly"
  nickname    = "Zoomify Pro yearly"

  recurring {
    interval = "year"
  }

  metadata = merge(local.common_metadata, {
    plan     = "pro"
    interval = "yearly"
  })
}

resource "stripe_webhook_endpoint" "billing" {
  count = var.create_webhook_endpoint ? 1 : 0

  url            = var.webhook_url
  description    = "${title(var.app_name)} ${var.environment} subscription webhook"
  enabled_events = local.webhook_events
}

data "external" "payment_links" {
  depends_on = [
    stripe_price.starter_monthly,
    stripe_price.starter_yearly,
    stripe_price.pro_monthly,
    stripe_price.pro_yearly,
  ]

  program = ["bash", "-lc", "cd ${abspath("${path.root}/../../..")} && uv run python ${abspath("${path.module}/scripts/payment_links.py")}"]

  query = {
    environment              = var.environment
    app_name                 = var.app_name
    stripe_api_key           = var.stripe_api_key
    starter_monthly_price_id = stripe_price.starter_monthly.id
    starter_yearly_price_id  = stripe_price.starter_yearly.id
    pro_monthly_price_id     = stripe_price.pro_monthly.id
    pro_yearly_price_id      = stripe_price.pro_yearly.id
  }
}
