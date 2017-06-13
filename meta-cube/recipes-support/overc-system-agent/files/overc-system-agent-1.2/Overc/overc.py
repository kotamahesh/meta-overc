import sys, os
import subprocess
from Overc.package import Package
from Overc.container import Container
from Overc.utils import Utils
from Overc.utils import ROOTMOUNT
from Overc.utils import HOSTPID
from Overc.utils  import SYSROOT
from Overc.utils import Process

def Is_btrfs():
    return not os.system('btrfs subvolume show %s >/dev/null 2>&1' % ROOTMOUNT)

def Is_lvm():
    #to be done
    return False

if Is_btrfs():
    from Overc.backends.btrfs import Btrfs as Host_update

#A placeholder for dealing with other supported filesystem's update, such as LVM etc.
elif Is_lvm():
    pass
else:
    Host_update = None

class Overc(object):
    def __init__(self):
        if Host_update is None:
            print "Error: Not using a supported filesystem!"
            sys.exit(1)
        self.agency = Host_update()
        self.package = Package()
        self.container = Container()
        self.utils = Utils()
        self.message = ""
        
        if not self.agency:
            print "Error: cannot get the right backends!"
            sys.exit(2)

        self.bakup_mode = self.agency.bakup_mode

    def help(self):
        if os.path.exists("/usr/bin/smart"):
            return _('OverC Management Tool for Host update')

    def set_args(self, args):
        self.args=args

        try:
            self.command = args.command
        except:
            self.command = None

    def system_upgrade(self):
        self._system_upgrade(self.args.template, self.args.reboot, self.args.force, self.args.skipscan, self.args.skip_del)

    def _system_upgrade(self, template, reboot, force, skipscan, skip_del):
	print "skipscan %d" % skipscan
        containers = self.container.get_container(template)
        overlay_flag = 0
	#By now only support "Pulsar" and "overc" Linux upgrading
        DIST = "Pulsar overc"
	upgrade_s = []
	os.system('rm -rf /etc/overc/upgrade.lock')
        for cn in containers:
            if self.container.is_active(cn, template):
	        for dist in DIST.split():
	            if dist in self.container.get_issue(cn, template).split():
                        print "Updating container %s" % cn

                        self._container_upgrade(cn, template, True, False, skip_del) #by now only rpm upgrade support
                        if self.retval is not 0:
                            print "*** Failed to upgrade container %s" % cn
                            print "*** Abort the system upgrade action"
			    print "rollback and reboot the system to the previous status"
			    for c in upgrade_s:
			        print "rollback container %s" % c
			        self._container_rollback(c, None, 'dom0', True)

                            self.message = "\nrebooting..."
			    print self.message
			    self.system_reboot()
                        else:
			    upgrade_s.append(cn)
			    os.system('echo %s >>/etc/overc/upgrade.lock' % cn)
                            if self.container.is_overlay(cn) > 0:
                                overlay_flag = 1
                        break

        rc = self._host_upgrade(0, force)
        if (rc == 2): #upgrade failed
	    print "Error: upgrade essentil system failed."
	    for c in upgrade_s:
	        print "rollback container %s" % c
		self._container_rollback(c, None, 'dom0', True)

	    self.message += "\nrebooting..."
	    print self.message
	    self.system_reboot()

        os.system('rm -rf /etc/overc/upgrade.lock')

        if ((overlay_flag == 1) and (skipscan == 0) and (rc == 1)):
		cmd = "lxc-overlayscan %s/%s" % (SYSROOT, self.agency.next_rootfs)
		process = Process()
		retval = process.run(cmd)

        if ((rc == 1) and (reboot != 0)):
            self.message += "\nrebooting..."
            print self.message
            self.system_reboot()

    def system_reboot(self):
        self.agency.sync()
        os.system('reboot')

    def system_rollback(self):
        containers = self.container.get_container(self.args.template)
        #By now only support "Pulsar" and "overc" Linux rollback
        DIST = "Pulsar overc"
        need_reboot=False
        for cn in containers:
            if self.container.is_active(cn, self.args.template):
                for dist in DIST.split():
                    if dist in self.container.get_issue(cn, self.args.template).split():
                        print "Rollback container %s" % cn
                        self._container_rollback(cn, None, self.args.template, True)
                        if self.retval is not 0:
                            print "*** Failed to rollback container %s" % cn
                        else:
                            need_reboot=True
                        break


        rc = self._host_rollback()
        if need_reboot or rc:
            self.message += "\nrebooting..."
            print self.message
            self.system_reboot()


    def factory_reset(self):
        rc = self.agency.factory_reset()
        if not rc:
           self.agency.clean_essential()
           self.agency.clean_container()
           self.message += self.agency.message
           print self.message
        else:
            self.message += "\nrebooting..."
            print self.message
            self.system_reboot()
                        
    def _need_upgrade(self):
        self.host_update()
        if self.host_newer() == 0:
            return True
        else:
            return False

    def host_status(self):
        print "host status"

    def host_newer(self):
        rc = self.utils._nsenter(HOSTPID,'smart newer')
        self.message += self.utils.message
        return rc

    def host_update(self):
        rc = self.utils._nsenter(HOSTPID, 'smart update')
        self.message += self.utils.message
        return rc

    def host_upgrade(self):
        self._host_upgrade(self.args.reboot, self.args.force)
        print self.message

    def _host_upgrade(self, reboot, force):
        if self._need_upgrade() or force:
            rc = self.agency.do_upgrade()
            self.message = self.agency.message
	    if not rc:
	        return 2
        else:
            self.message = "There is no new system available to upgrade!"
	    return 0

	if reboot:
	    self.message += "\nrebooting..."
	    print self.message
	    self.system_reboot()
	return 1
	         
    def host_rollback(self):
        rc = self._host_rollback()
        print self.message
        if rc:
            self.system_reboot()

    def _host_rollback(self):
        if self.bakup_mode:
            self.message = "Error: You are running in the backup mode, cannot do rollback!"
            print self.message
            return

        print "host rollback"
        rc = self.agency.do_rollback()
        self.message = self.agency.message
        return rc 
 
    def container_rollback(self):
        self._container_rollback(self.args.name, self.args.snapshot_name, self.args.template, False)
        sys.exit(self.retval)
    def _container_rollback(self, container, snapshot, template, force):
        self.retval = self.container.rollback(container, snapshot, template, force)
        self.message = self.container.message

    def container_list(self):
        self._container_list(self.args.template)
        sys.exit(self.retval)
    def _container_list(self, template):
        self.retval = self.container.list(template)
        self.message = self.container.message

    def container_snapshot_list(self):
        self._container_snapshot_list(self.args.name, self.args.template)
        sys.exit(self.retval)
    def _container_snapshot_list(self, container, template):
        self.retval = self.container.list_snapshot(container, template)
        self.message = self.container.message

    def container_snapshot(self):
        self._container_snapshot(self.args.name, self.args.template)
        sys.exit(self.retval)
    def _container_snapshot(self, container, template):
        self.retval = self.container.snapshot(container, template)
        self.message = self.container.message

    def container_activate(self):
        self._container_activate(self.args.name, self.args.template, self.args.force)
        sys.exit(self.retval)
    def _container_activate(self, container, template, force):
        self.retval = self.container.activate(container, template, force)
        self.message = self.container.message

    def container_start(self):
        self._container_start(self.args.name, self.args.template)
        sys.exit(self.retval)
    def _container_start(self, container, template):
        self.retval = self.container.start(container, template)
        self.message = self.container.message

    def container_stop(self):
        self._container_stop(self.args.name, self.args.template)
        sys.exit(self.retval)
    def _container_stop(self, container, template):
        self.retval = self.container.stop(container, template)
        self.message = self.container.message

    def container_update(self):
        self._container_update(self.args.template)
        sys.exit(self.retval)
    def _container_update(self, template):
        self.retval = self.container.update(template)
        self.message = self.container.message

    def container_send_image(self):
        self._container_send_image(self.args.template, self.args.image_url)
        sys.exit(self.retval)
    def _container_send_image(self, template, url):
        self.retval = self.container.send_image(template, url)
        self.message = self.container.message

    def container_delete(self):
        self._container_delete(self.args.name, self.args.template, self.args.force)
        sys.exit(self.retval)
    def _container_delete(self, container, template, force):
        self.retval = self.container.delete(container, template, force)
        self.message = self.container.message

    def container_upgrade(self):
        # Perform overlay check fist
        overlaylist = self.container.get_overlay(self.args.name)
        if len(overlaylist)>0:
            print "Container %s has overlayed dir, including" % self.args.name
            print(overlaylist)
            print "This container can only be upgraded via a system upgrade"
            self.retval = 0
        else:
            self._container_upgrade(self.args.name, self.args.template, self.args.rpm, self.args.image, self.args.skip_del)
        sys.exit(self.retval)
    def _container_upgrade(self, container, template, rpm=True, image=False, skip_del=False):
        self.retval = self.container.upgrade(container, template, rpm, image, skip_del)
        self.message = self.container.message

    def container_delete_snapshots(self):
        self._container_delete_snapshots(self.args.name, self.args.template)
        sys.exit(self.retval)
    def _container_delete_snapshots(self, container, template):
        self.retval = self.container.delete_snapshots(container, template)
        self.message = self.container.message
    def container_overlay(self):
        # Parser commnand, create or restore
        if self.args.ollist:
	    self._container_overlay_list(self.args.name)
        elif self.args.olstop:
            self._container_overlay_stop(self.args.name, self.args.oldir)
        else :
            self._container_overlay_create(self.args.name, self.args.oldir, self.args.olsource)
    def _container_overlay_list(self, container):
	# List overlay dir in container
        print "overlayed directories in %s including:" % container
        print ",".join(self.container.get_overlay(container))

    def _container_overlay_create(self, container, dirs, source):
        # Create overlay dir in container
        self.retval = self.container.overlay_create(container, dirs, source)
    def _container_overlay_stop(self, container, dirs):
        # Restore overlay-ed dir
        self.retval = self.container.overlay_stop(container, dirs)

