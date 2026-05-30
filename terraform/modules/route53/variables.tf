variable "zone_id" {
  type        = string
  description = "Route 53 hosted zone ID (e.g. zynclo.com)."
}

variable "record_names" {
  type        = list(string)
  description = "Static CNAME record names (FQDN) — required for for_each at plan time."
}

variable "record_targets" {
  type        = map(string)
  description = "Map of record name -> CNAME target hostname."
}

variable "ttl" {
  type        = number
  default     = 300
  description = "DNS TTL in seconds."
}
