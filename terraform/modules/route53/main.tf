resource "aws_route53_record" "cname" {
  for_each = toset(var.record_names)

  zone_id = var.zone_id
  name    = each.key
  type    = "CNAME"
  ttl     = var.ttl
  records = [var.record_targets[each.key]]
}

# TXT records (e.g. Railway `_railway-verify.<host>` domain-ownership records).
# allow_overwrite adopts a record that may already exist outside Terraform.
resource "aws_route53_record" "txt" {
  for_each = toset(var.txt_record_names)

  zone_id         = var.zone_id
  name            = each.key
  type            = "TXT"
  ttl             = var.ttl
  records         = [var.txt_record_values[each.key]]
  allow_overwrite = true
}
