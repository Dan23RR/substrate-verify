variable "vpc_id" {
  description = "The ID of the associated VPC"
}

variable "subnet_ids" {
  description = "A list of Subnet IDs to apply the ACL to"
  type        = list(string)
  default     = []
}

variable "ingress" {
  description = "Specifies an ingress rule"
  default     = []
  type        = any
}

variable "egress" {
  description = "Specifies an egress rule"
  default     = []
  type        = any
}

variable "tags" {
  description = "A mapping of tags to assign to the resource."
  type        = map(string)
  default     = {}
}