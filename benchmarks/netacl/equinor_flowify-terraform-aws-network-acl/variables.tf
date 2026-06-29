variable "region" {
  type        = string
  default     = "us-west-2"
  description = "The region where AWS operations will take place"
}

variable "vpc_id" {
  type        = string
  description = "ID of the VPC where to create Network ACL"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "A list of Public subnet IDs to apply the ACL to"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "A list of Private subnet IDs to apply the ACL to"
}

variable "public_dedicated_network_acl" {
  description = "Whether to use dedicated network ACL (not default) and custom rules for public subnets"
  default     = false
}

variable "private_dedicated_network_acl" {
  description = "Whether to use dedicated network ACL (not default) and custom rules for private subnets"
  default     = false
}

variable "common_tags" {
  type        = map(string)
  description = "The default tags that will be added to all taggable resources"

  default = {
    EnvClass    = "dev"
    Environment = "Playground"
    Owner       = "Ops"
    Terraform   = "true"
  }
}

variable "env_name" {
  type        = string
  default     = "playground"
  description = "The description that will be applied to the tags for resources created in the SG configuration"
}

variable "public_inbound_acl_rules" {
  type        = list(any)
  description = "Public subnets inbound network ACLs"

  default = [
    {
      rule_number = 1
      rule_action = "allow"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_block  = "0.0.0.0/0"
    },
  ]
}

variable "public_outbound_acl_rules" {
  type        = list(any)
  description = "Public subnets outbound network ACLs"

  default = [
    {
      rule_number = 100
      rule_action = "allow"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_block  = "0.0.0.0/0"
    },
  ]
}

variable "private_inbound_acl_rules" {
  type        = list(any)
  description = "Private subnets inbound network ACLs"

  default = [
    {
      rule_number = 100
      rule_action = "allow"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_block  = "0.0.0.0/0"
    },
  ]
}

variable "private_outbound_acl_rules" {
  type        = list(any)
  description = "Private subnets outbound network ACLs"

  default = [
    {
      rule_number = 100
      rule_action = "allow"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_block  = "0.0.0.0/0"
    },
  ]
}

