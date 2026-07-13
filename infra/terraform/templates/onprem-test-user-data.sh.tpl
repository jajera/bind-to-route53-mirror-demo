#!/bin/bash
set -eux
echo "nameserver ${bind_ip}" >/etc/resolv.conf
dnf install -y bind-utils
