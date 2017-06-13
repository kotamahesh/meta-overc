#!/bin/bash
cn=""

if [ -f /etc/overc/upgrade.lock ]; then 
	cn=$(cat /etc/overc/upgrade.lock)
fi

for i in $cn; do 
	/opt/overc-installer/overc-cctl rollback -n $i -F -r 
done

rm -rf /etc/overc/upgrade.lock

if [ -n "$cn" ]; then
	reboot
fi
