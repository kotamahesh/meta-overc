FILESEXTRAPATHS_prepend := "${THISDIR}/files:"

SRC_URI += "file://0001-xfsettingsd-use-gnome-as-default-icon-theme.patch"

RRECOMMENDS_${PN} += "gnome-icon-theme"
