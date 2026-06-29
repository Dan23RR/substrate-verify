# _terraform-module-aws-network-acl_
_Terraform module Provides an_ **_Network ACL_** _resource in_ **_AWS_** _cloud provider. You might set up network ACLs with rules similar to your security groups in order to add an additional layer of security to your VPC._


<!--BEGIN STABILITY BANNER-->
---

![_Code : Stable_](https://img.shields.io/badge/Code-Stable-brightgreen?style=for-the-badge&logo=github)

>

---
<!--END STABILITY BANNER-->

## _General_

_This module can be used to deploy a_ **_Network ACL_** _on AWS Cloud Provider......_


---

## _Prerequisites_

_This module needs **_Terraform 0.12.23_** or newer._
_You can download the latest Terraform version from_ [_here_](https://www.terraform.io/downloads.html).



---

## _Features Branches_

_Below we are able to check the resources that are being created as part of this module call:_

- **_Network ACL_**


---

## _Usage_

## _Using this repo_

_To use this module, add the following call to your code:_

- **_Sample Code:_**

```tf
module "network_acl" {
  source = "git::https://github.com/nitinda/terraform-module-aws-network-acl.git?ref=master"
  
  vpc_id = var.vpc_id
}

```

```tf
module "network_acl" {
  source = "git::https://github.com/nitinda/terraform-module-aws-network-acl.git?ref=master"
  
  vpc_id     = module.vpc.id
  subnet_ids = [module.vpc_subnet_public_1a.id, module.vpc_subnet_public_1b.id]

  egress = [
    {
      protocol   = "all"
      rule_no    = 100
      action     = "allow"
      cidr_block = "0.0.0.0/0"
      from_port  = 0
      to_port    = 0
    }
  ]

  ingress = [
    {
      protocol   = "all"
      rule_no    = 100
      action     = "allow"
      cidr_block = "0.0.0.0/0"
      from_port  = 0
      to_port    = 0
    }
  ]

  tags = merge(
    var.common_tags,
    {
      Environment = "prod"
      Name        = "network-acl"
    }
  )
}

```


---

## _Inputs_

_The variables required in order for the module to be successfully called from the deployment repository are the following:_

|**_Variable_** | **_Description_** | **_Type_** | **_Argument Status_** | **_Default Value_** |
|:----|:----|-----:|:---:|:---:|
| **_vpc\_id_** | _The ID of the associated VPC_ | _string_ | **_Required_** |  |
| **_subnet\_ids_** | _A list of Subnet IDs to apply the ACL to_ | _list(string)_ | **_Optional_** | **_[]_** |
| **_ingress_** | _Specifies an ingress rule_ | _any_ | **_Optional_** | **_[]_** |
| **_egress_** | _Specifies an egress rule_ | _any_ | **_Optional_** | **_[]_** |
| **_tags_** | _A mapping of tags to assign to the resource_ | _map(string)_ | **_Optional_** | **_{}_** |


---


## _Outputs_

### _General_

_This module has the following outputs:_

* **_id_**


---

### _Usage_

_In order for the variables to be accessed at module level please use the syntax below:_

```tf
module.<module_name>.<output_variable_name>
```


_The output variable is able to be accessed through terraform state file using the syntax below:_

```tf
data.terraform_remote_state.<layer_name>.<output_variable_name>
```

---



## _Authors_

_Module maintained by Module maintained by the -_ **_Nitin Das_**