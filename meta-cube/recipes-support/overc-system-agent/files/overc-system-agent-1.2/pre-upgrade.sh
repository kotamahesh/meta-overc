#!/bin/bash

CNS=`/etc/overc/container/dom0 -L | sed '1d' | awk '{print $1}'`

for cn in $CNS; do
	cat /var/lib/lxc/$cn/fstab | grep smart	>/dev/null
	if [ ! "$?" -eq  "0" ]; then
		echo "/var/lib/smart /var/lib/lxc/$cn/rootfs/var/lib/smart none bind 0 0" >>/var/lib/lxc/$cn/fstab
	fi
done

sed -i '/OVERCCN/d' /essential/etc/fstab
echo "LABEL=OVERCCN /var/lib/lxc btrfs defaults,compress=lzo 0 1" >>/essential/etc/fstab

smart update;smart upgrade -y overc-system-agent
reboot
