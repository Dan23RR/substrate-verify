# AWS Network ACLs Terraform module

Author: [Yurii Onuk](https://onuk.org.ua)

Terraform module which creates [Network ACLs with rules](https://www.terraform.io/docs/providers/aws/r/network_acl.html)

Next types of resources are supported:

* [AWS Network ACLs](https://www.terraform.io/docs/providers/aws/r/network_acl.html)
* [AWS Network ACL Rules](https://www.terraform.io/docs/providers/aws/r/network_acl_rule.html)

## Terraform version compatibility

- 0.12.29
- 1.1.5

## Usage

main.tf:

```hcl-terraform
module "network-acl" {
  source                  = "git@github.com:equinor/flowify-terraform-aws-network-acl.git/?ref=x.x.x"
  
  region                  = "${var.region}"
  env_name                = "${var.env_name}"

  # VPC
  vpc_id                  = "${module.vpc.vpc_id}"

  # Subnet IDs
  public_subnet_ids       = ["${module.vpc.public_subnet_id_list}"]
  private_subnet_ids      = ["${module.vpc.private_subnet_id_list}"]

  # Turn on/off Network ACLs
  public_dedicated_network_acl    = "${var.public_dedicated_network_acl}"
  private_dedicated_network_acl   = "${var.private_dedicated_network_acl}"

  # Tags
  common_tags = "${var.common_tags}"

  # Rules for Public ACLs rules
  public_inbound_acl_rules    = "${local.public_network_acls["public_inbound"]}"
  public_outbound_acl_rules   = "${local.public_network_acls["public_outbound"]}"

  # Rules for Private ACLs rules
  private_inbound_acl_rules   = "${local.private_network_acls["private_inbound"]}"
  private_outbound_acl_rules  = "${local.private_network_acls["private_outbound"]}"
}

locals {
    public_network_acls = {
      public_inbound = [
        {
          rule_number = 100
          rule_action = "allow"
          from_port   = 32768
          to_port     = 61000
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
        {
          rule_number = 104
          rule_action = "allow"
          from_port   = 32768
          to_port     = 61000
          protocol    = "17"
          cidr_block  = "0.0.0.0/0"
        },
        {
          rule_number = 110
          rule_action = "allow"
          from_port   = 80
          to_port     = 80
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
        # For test allow SSH port
        {
          rule_number = 120
          rule_action = "allow"
          from_port   = 22
          to_port     = 22
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
      ]
      public_outbound = [
        {
          rule_number = 100
          rule_action = "allow"
          from_port   = 32768
          to_port     = 61000
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
        {
          rule_number = 104
          rule_action = "allow"
          from_port   = 32768
          to_port     = 61000
          protocol    = "17"
          cidr_block  = "0.0.0.0/0"
        },
        {
          rule_number = 200
          rule_action = "allow"
          from_port   = 80
          to_port     = 80
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
        {
          rule_number = 201
          rule_action = "allow"
          from_port   = 443
          to_port     = 443
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
      ]
    }

    private_network_acls = {
      private_inbound = [
        {
          rule_number = 100
          rule_action = "allow"
          from_port   = 1024
          to_port     = 65535
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
        {
          rule_number = 104
          rule_action = "allow"
          from_port   = 1024
          to_port     = 65535
          protocol    = "17"
          cidr_block  = "0.0.0.0/0"
        },
        {
          rule_number = 110
          rule_action = "allow"
          from_port   = 443
          to_port     = 443
          protocol    = "6"
          cidr_block  = "${module.vpc.vpc_cidr_block}"
        },
        {
          rule_number = 120
          rule_action = "allow"
          from_port   = 8443
          to_port     = 8443
          protocol    = "6"
          cidr_block  = "${module.vpc.vpc_cidr_block}"
        },
      ]
      private_outbound = [
        {
          rule_number = 100
          rule_action = "allow"
          from_port   = 1024
          to_port     = 65535
          protocol    = "6"
          cidr_block  = "${module.vpc.vpc_cidr_block}"
        },
        {
          rule_number = 110
          rule_action = "allow"
          from_port   = 88
          to_port     = 88
          protocol    = "6"
          cidr_block  = "${module.vpc.vpc_cidr_block}"
        },
        {
          rule_number = 120
          rule_action = "allow"
          from_port   = 80
          to_port     = 80
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
        {
          rule_number = 130
          rule_action = "allow"
          from_port   = 443
          to_port     = 443
          protocol    = "6"
          cidr_block  = "0.0.0.0/0"
        },
      ]
    }
  }
```

variable.tf:

```hcl-terraform
variable "env_name" {
  type        = "string"
  description = "The description that will be applied to the tags for resources created in the vpc configuration"
  default    = "playground"
}

variable "common_tags" {
  type = "map"

  default = {
    EnvClass    = "dev"
    Environment = "Playground"
    Owner       = "Ops"
    Terraform   = "true"
  }

  description = "A default map of tags to add to all resources"
}

variable "public_dedicated_network_acl" {
  description = "Whether to use dedicated network ACL (not default) and custom rules for public subnets"
  default     = false
}

variable "private_dedicated_network_acl" {
  description = "Whether to use dedicated network ACL (not default) and custom rules for private subnets"
  default     = false
}
```

output.tf:

```hcl-terraform
output "public_network_acl_id" {
  value       = "${module.network-acl.public_network_acl_id}"
  description = "ID of the public network ACL"
}

output "private_network_acl_id" {
  value       = "${module.network-acl.private_network_acl_id}"
  description = "ID of the private network ACL"
}
```

terraform.tfvars:

```hcl-terraform
region  = "us-west-1"

# Name to be used on all the resources as identifier
env_name = "usw201"

common_tags = {
    EnvClass    = "dev"
    Environment = "usw201"
    Owner       = "Engineering"
    Terraform   = "true"
}

# Network ACLs
# Redefining default values for inputs variables
public_dedicated_network_acl    = true
private_dedicated_network_acl   = true
```

## Inputs

 Variable                        | Type     | Default                               | Required | Purpose
:------------------------------- |:--------:| ------------------------------------- | -------- | :----------------------
`env_name`                       | `string` | `playground`                          |   `no`   | `The description that will be applied to the tags for resources created in the vpc configuration` |
`vpc_id`                         | `string` | `no`                                  |   `yes`  | `ID of the VPC where to create Network ACLs` |
`public_subnet_ids`              | `list`   | `no`                                  |   `yes`  | `A list of Public subnet IDs to apply the ACL to` |
`private_subnet_ids`             | `list`   | `no`                                  |   `yes`  | `A list of Private subnet IDs to apply the ACL to` |
`public_dedicated_network_acl`   | `string` | `false`                               |   `no`   | `Whether to use dedicated network ACL (not default) and custom rules for public subnets` |
`private_dedicated_network_acl`  | `string` | `false`                               |   `no`   | `Whether to use dedicated network ACL (not default) and custom rules for private subnets` |
`common_tags`                    | `map`    | `yes`                                 |   `no`   | `The common tags that will be added to all taggable resources` |
`public_inbound_acl_rules`       | `list`   | `yes`                                 |   `no`   | `Public subnets inbound network ACLs` |
`public_outbound_acl_rules`      | `list`   | `yes`                                 |   `no`   | `Public subnets outbound network ACLs` |
`private_inbound_acl_rules`      | `list`   | `yes`                                 |   `no`   | `Private subnets inbound network ACLs` |
`private_outbound_acl_rules`     | `list`   | `yes`                                 |   `no`   | `Private subnets outbound network ACLs` |
        
## Outputs

| Name                        | Description                         |
| --------------------------- | ----------------------------------- |
| `public_network_acl_id`     | `ID of the public network ACL`      |
| `private_network_acl_id`    | `ID of the private network ACL`     |

## Terraform Validate Action

Runs `terraform validate -var-file=validator` to validate the Terraform files 
in a module directory via CI/CD pipeline.
Validation includes a basic check of syntax as well as checking that all variables declared.

### Success Criteria

This action succeeds if `terraform validate -var-file=validator` runs without error.

### Validator

If some variables are not set as default, we should fill the file `validator` with these variables.
