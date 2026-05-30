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
  }
}
