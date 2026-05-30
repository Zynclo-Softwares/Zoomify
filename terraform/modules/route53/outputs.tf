output "record_names" {
  description = "DNS record names managed in Route 53."
  value       = sort(keys(aws_route53_record.cname))
}

output "record_count" {
  description = "Number of CNAME records created/updated."
  value       = length(aws_route53_record.cname)
}
