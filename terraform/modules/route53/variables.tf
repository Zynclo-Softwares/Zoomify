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

variable "txt_record_names" {
  type        = list(string)
  default     = []
  description = "Static TXT record names (FQDN) — required for for_each at plan time."
}

variable "txt_record_values" {
  type        = map(string)
  default     = {}
  description = "Map of TXT record name -> unquoted record value (e.g. railway-verify=...)."
}

variable "ttl" {
  type        = number
  default     = 300
  description = "DNS TTL in seconds."
}
