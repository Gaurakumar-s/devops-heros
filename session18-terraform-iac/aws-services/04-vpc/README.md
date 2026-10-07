# 04 – VPC (Virtual Private Cloud) – Networking

## What is VPC?
A VPC is your own isolated network inside an AWS region: a private IP range that you carve into subnets, with your own route tables, gateways and firewalls. EC2 instances, RDS databases, EKS nodes, Lambda-in-VPC, load balancers – everything with a network interface lives in a VPC. Every account gets a *default VPC* per region; real projects create their own (as Session 19 does with Terraform).

```text
Region ap-south-1
└── VPC 10.20.0.0/16
    ├── public subnet  10.20.1.0/24 (AZ a) ── route 0.0.0.0/0 → Internet Gateway
    │     └── EC2 web (public IP)
    ├── private subnet 10.20.2.0/24 (AZ a) ── route 0.0.0.0/0 → NAT Gateway
    │     └── RDS / app servers (no public IP)
    ├── Internet Gateway
    ├── NAT Gateway (sits in the public subnet, has an Elastic IP)
    ├── route tables, security groups, network ACLs
    └── (optional) VPC endpoints to S3/DynamoDB so traffic never leaves AWS
```

## CIDR
Classless Inter-Domain Routing notation: `10.20.0.0/16` = network `10.20.0.0`, first 16 bits fixed, 2^(32-16) = 65,536 addresses. A VPC CIDR can be /16 (largest) to /28 (smallest); use RFC 1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) and make sure it does not overlap with other VPCs/on-prem networks you may peer with later.

| CIDR | Addresses | Usable in a subnet (AWS reserves 5) |
|---|---|---|
| /16 | 65,536 | – (VPC size) |
| /20 | 4,096 | 4,091 |
| /24 | 256 | 251 |
| /28 | 16 | 11 |

AWS reserves in every subnet: `.0` (network), `.1` (VPC router), `.2` (DNS), `.3` (future), `.255` (broadcast).

## Subnets
A subnet is a slice of the VPC CIDR placed in **one availability zone**. Resources are launched into subnets, so subnets decide the AZ (fault domain) and, through their route table, whether a resource can be reached from the internet.

- Spread subnets across at least 2 AZs for anything that must survive an AZ outage (ALB requires 2 AZs).
- Typical layout per AZ: one public subnet (load balancers, NAT, bastion), one private subnet (apps), one isolated subnet (databases).
- `map_public_ip_on_launch = true` on public subnets so instances get a public IPv4 automatically.

```hcl
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.20.1.0/24"
  availability_zone       = "ap-south-1a"
  map_public_ip_on_launch = true
}
```

## Route tables
Each subnet is associated with exactly one route table (the VPC's *main* table if you do not associate another). A route table is a list of `destination CIDR → target`. The most specific prefix wins; the `local` route for the VPC CIDR is always present and cannot be removed.

| Destination | Target | Meaning |
|---|---|---|
| `10.20.0.0/16` | local | everything inside the VPC (automatic) |
| `0.0.0.0/0` | igw-… | internet via Internet Gateway → this is a **public** route table |
| `0.0.0.0/0` | nat-… | internet via NAT Gateway → **private** route table |
| `10.30.0.0/16` | pcx-… | another VPC through peering |
| `pl-…` (S3 prefix list) | vpce-… | S3 through a gateway endpoint |

```hcl
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0"; gateway_id = aws_internet_gateway.main.id }
}
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
```

## Internet Gateway
A horizontally scaled, highly available VPC component (one per VPC) that lets resources with **public IPs** talk to the internet in both directions. It performs the 1:1 NAT between the instance's private IP and its public/Elastic IP. No bandwidth limit, no cost. Attach it to the VPC, then add the `0.0.0.0/0 → igw` route to the subnets that should be public.

## NAT Gateway
A managed NAT device for **private** subnets: instances without a public IP can reach the internet (apt/yum updates, Docker Hub, external APIs) while nothing on the internet can initiate connections to them.

- Lives in a **public** subnet, needs an **Elastic IP**, and is AZ-specific (one per AZ for HA).
- Charged per hour and per GB processed – the single most common surprise on a dev bill. Shut it down or use a NAT instance / VPC endpoints for cheap labs.
- IPv6 uses an *egress-only internet gateway* instead.

```hcl
resource "aws_eip" "nat" { domain = "vpc" }
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id
  depends_on    = [aws_internet_gateway.main]
}
```

## Security Groups
Instance-level (ENI-level) **stateful** firewall; allow rules only; inbound and outbound evaluated separately; can reference other SGs (`source = sg-app`) and prefix lists. Default SG: all outbound allowed, inbound only from itself. One instance can have up to 5 SGs. Changes apply immediately. Details and examples in `../02-ec2/README.md`.

## Network ACLs
Subnet-level **stateless** firewall with numbered **allow and deny** rules evaluated in order (lowest number first, first match wins, `*` rule denies the rest). Stateless means return traffic must be explicitly allowed too (ephemeral ports 1024–65535). The default NACL allows everything; custom NACLs deny everything until you add rules.

| | Security Group | Network ACL |
|---|---|---|
| Scope | instance / ENI | subnet |
| State | stateful | stateless |
| Rules | allow only | allow + deny, ordered |
| Typical use | per-app firewall | coarse subnet guardrail, blocking a bad IP range |

Use SGs for almost everything; use NACLs to block an abusive CIDR or enforce "database subnet only talks to app subnet".

## Public vs private subnet
The subnet itself has no "public" flag. It is public **if its route table has a route to an Internet Gateway**, otherwise it is private.

| | Public subnet | Private subnet |
|---|---|---|
| Route `0.0.0.0/0` | → Internet Gateway | → NAT Gateway (or no route = isolated) |
| Instances get public IP | yes (`map_public_ip_on_launch`) | no |
| Reachable from internet | yes, if SG allows | never directly |
| Can reach internet | yes | only outbound through NAT |
| Hosts | ALB/NLB, NAT Gateway, bastion, public web servers | app servers, EKS nodes, caches, databases (often an *isolated* subnet with no NAT at all) |

Best practice: keep everything private, expose only a load balancer in the public subnets, and use VPC endpoints (S3, DynamoDB, ECR, SSM) so private subnets do not even need a NAT for AWS traffic.

## Extra pieces worth knowing
- **VPC Flow Logs** → CloudWatch/S3 to see accepted/rejected traffic (the first thing to check when "it cannot connect").
- **VPC Peering** / **Transit Gateway** to connect VPCs; **Site-to-Site VPN** / **Direct Connect** to on-prem.
- **DNS**: `enable_dns_support` + `enable_dns_hostnames` so instances get `ip-10-20-1-12.ap-south-1.compute.internal` names and private hosted zones work.
- **Elastic Network Interface (ENI)**: the actual NIC; SGs, private IPs and public IPs attach to it.

## The Session 19 Terraform project in one picture
```text
aws_vpc.main (10.20.0.0/16)
 ├── aws_subnet.public (10.20.1.0/24, ap-south-1a, public IPs on)
 ├── aws_internet_gateway.main
 ├── aws_route_table.public (0.0.0.0/0 → igw) + association to the public subnet
 ├── aws_security_group.web (22 from my IP, 80/443 from anywhere, all egress)
 ├── aws_instance.web (t3.micro in the public subnet, SG web, user data installs nginx)
 └── aws_s3_bucket.app_data (private bucket the instance could read via an IAM role)
```
