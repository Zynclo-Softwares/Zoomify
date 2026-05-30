terraform {
  required_version = ">= 1.5.0"

  required_providers {
    stripe = {
      source  = "stripe/stripe"
      version = "~> 0.1"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
    railway = {
      source  = "terraform-community-providers/railway"
      version = "~> 0.4"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "stripe" {
  api_key = local.stripe_api_key
}

provider "railway" {
  # Uses RAILWAY_TOKEN from the shell environment (export in ~/.zshrc or similar).
}

provider "aws" {
  # Uses AWS CLI credentials (same as `aws route53 ...`).
}
