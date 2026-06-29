#######################################
# ACL Terraform Module                #
# Valid for both Tf 0.12.29 and 1.1.5 #
#######################################

provider "aws" {
  region = var.region
}

########################
# Public Network ACLs
########################

resource "aws_network_acl" "public" {
  count = var.public_dedicated_network_acl ? 1 : 0

  vpc_id     = var.vpc_id
  subnet_ids = var.public_subnet_ids

  tags = merge(
    var.common_tags,
    {
      "Name" = "${var.env_name}-public-acl"
    },
  )
}

resource "aws_network_acl_rule" "public_inbound" {
  count = var.public_dedicated_network_acl ? length(var.public_inbound_acl_rules) : 0

  network_acl_id = aws_network_acl.public[0].id
  egress         = false

  rule_number = var.public_inbound_acl_rules[count.index]["rule_number"]
  rule_action = var.public_inbound_acl_rules[count.index]["rule_action"]
  from_port   = var.public_inbound_acl_rules[count.index]["from_port"]
  to_port     = var.public_inbound_acl_rules[count.index]["to_port"]
  protocol    = var.public_inbound_acl_rules[count.index]["protocol"]
  cidr_block  = var.public_inbound_acl_rules[count.index]["cidr_block"]
}

resource "aws_network_acl_rule" "public_outbound" {
  count = var.public_dedicated_network_acl ? length(var.public_outbound_acl_rules) : 0

  network_acl_id = aws_network_acl.public[0].id
  egress         = true

  rule_number = var.public_outbound_acl_rules[count.index]["rule_number"]
  rule_action = var.public_outbound_acl_rules[count.index]["rule_action"]
  from_port   = var.public_outbound_acl_rules[count.index]["from_port"]
  to_port     = var.public_outbound_acl_rules[count.index]["to_port"]
  protocol    = var.public_outbound_acl_rules[count.index]["protocol"]
  cidr_block  = var.public_outbound_acl_rules[count.index]["cidr_block"]
}

#######################
# Private Network ACLs
#######################

resource "aws_network_acl" "private" {
  count = var.private_dedicated_network_acl ? 1 : 0

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  tags = merge(
    var.common_tags,
    {
      "Name" = "${var.env_name}-private-acl"
    },
  )
}

resource "aws_network_acl_rule" "private_inbound" {
  count = var.private_dedicated_network_acl ? length(var.private_inbound_acl_rules) : 0

  network_acl_id = aws_network_acl.private[0].id
  egress         = false

  rule_number = var.private_inbound_acl_rules[count.index]["rule_number"]
  rule_action = var.private_inbound_acl_rules[count.index]["rule_action"]
  from_port   = var.private_inbound_acl_rules[count.index]["from_port"]
  to_port     = var.private_inbound_acl_rules[count.index]["to_port"]
  protocol    = var.private_inbound_acl_rules[count.index]["protocol"]
  cidr_block  = var.private_inbound_acl_rules[count.index]["cidr_block"]
}

resource "aws_network_acl_rule" "private_outbound" {
  count = var.private_dedicated_network_acl ? length(var.private_outbound_acl_rules) : 0

  network_acl_id = aws_network_acl.private[0].id
  egress         = true

  rule_number = var.private_outbound_acl_rules[count.index]["rule_number"]
  rule_action = var.private_outbound_acl_rules[count.index]["rule_action"]
  from_port   = var.private_outbound_acl_rules[count.index]["from_port"]
  to_port     = var.private_outbound_acl_rules[count.index]["to_port"]
  protocol    = var.private_outbound_acl_rules[count.index]["protocol"]
  cidr_block  = var.private_outbound_acl_rules[count.index]["cidr_block"]
}

