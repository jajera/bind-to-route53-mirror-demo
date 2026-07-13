---
inclusion: auto
description: Architecture diagrams — draw.io with official AWS icons, dark-mode aware
---

# Architecture diagrams

When creating or updating architecture diagrams for this repo (or sibling jajera AWS demos):

## Format

- Prefer **draw.io** (`.drawio`) under `docs/diagrams/`.
- Do **not** use Mermaid for the primary topology diagram.
- Link the `.drawio` from `docs/ARCHITECTURE.md` (and README if needed).
- Icon browser: [jajera AWS Icons](https://jajera.github.io/aws-icons) (official AWS Architecture Icons).
- Canonical example: `docs/diagrams/architecture.drawio`.

## Dark mode

Use `light-dark()` for adaptive contrast:

- Account / outer containers: `fillColor=#f5f5f5;strokeColor=light-dark(#666666,#D4D4D4)`
- VPC: `fillColor=light-dark(#8C4FFF0D,#8C4FFF0D);strokeColor=#8C4FFF;fillStyle=auto`
- Edge labels: `labelBackgroundColor=light-dark(#FFFFFF,#232F3E)` and adaptive `fontColor=light-dark(...)`
- Never rely on white-only label backgrounds without a dark counterpart

## Layout and icons

- Title (28px bold) + subtitle (14px) + orange separator (`strokeColor=#FF9900`)
- `fontFamily=Helvetica` everywhere
- Service icons: 48×48 `shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.<service>` inside category tint containers (120–140px), icon at ~(36–46, 30–36)
- Category tints: Compute `#FFF2E8`/`#ED7100`, Networking `#EDE7F6`/`#8C4FFF`, App Integration `#FCE4EC`/`#E7157B`, Security `#FFEBEE`/`#DD344C`
- Account boxes label: `profile · region · CIDR`
- Edge style: `edgeStyle=orthogonalEdgeStyle;rounded=1`

## This demo topology

Two accounts over Site-to-Site VPN:

| Side | Key nodes |
| --- | --- |
| On-prem | BIND EC2, VPN appliance (Libreswan CGW), optional dig client |
| Workload | VGW / Site-to-Site VPN, EventBridge → Lambda sync, NAT → Route 53 PHZ `corp.internal`, test EC2 |

Flows: AXFR over VPN; Route 53 **API via NAT** (not a Route 53 VPC endpoint); workload dig via AmazonProvidedDNS.
