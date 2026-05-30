resource "aws_route53_record" "cname" {
  for_each = toset(var.record_names)

  zone_id = var.zone_id
  name    = each.key
  type    = "CNAME"
  ttl     = var.ttl
  records = [var.record_targets[each.key]]
}
