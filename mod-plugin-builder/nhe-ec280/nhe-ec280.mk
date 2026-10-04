######################################
#
# nhe-ec280
#
# Electronic Echo 280 by New Horizon Electronics
# https://github.com/Kiwooky/NHE-EC280
#
# This file is the plugin's package for mod-plugin-builder
# (plugins/package/nhe-ec280/nhe-ec280.mk). The same file can be
# uploaded to https://builder.mod.audio/buildroot to get an install link.
#
# Set NHE_EC280_VERSION to the full hash of the commit to build.
#
######################################

NHE_EC280_VERSION = COMMIT_HASH_HERE
NHE_EC280_SITE = $(call github,Kiwooky,NHE-EC280,$(NHE_EC280_VERSION))
NHE_EC280_BUNDLES = nhe-ec280.lv2

NHE_EC280_TARGET_MAKE = $(TARGET_MAKE_ENV) $(TARGET_CONFIGURE_OPTS) $(MAKE) NOOPT=true -C $(@D)

define NHE_EC280_BUILD_CMDS
	$(NHE_EC280_TARGET_MAKE)
endef

define NHE_EC280_INSTALL_TARGET_CMDS
	$(NHE_EC280_TARGET_MAKE) install DESTDIR=$(TARGET_DIR) PREFIX=/usr
endef

$(eval $(generic-package))
