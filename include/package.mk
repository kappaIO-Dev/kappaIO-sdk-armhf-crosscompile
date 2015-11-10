PKG_JOBS?=-j1
MAKE_PATH?=./
MAKE_VARS?= \
	CFLAGS="$(CC_INCLUDE_DIR)" \
	CXXFLAGS="$(CC_INCLUDE_DIR)" \
	INCLUDE_DIR="$(CC_INCLUDE_DIR)"
export SH_FUNC:=. $(INCLUDE_DIR)/shell.sh;
STAMP_PREPARED=$(PKG_BUILD_DIR)/.prepared
STAMP_CONFIGURED:=$(PKG_BUILD_DIR)/.configured
STAMP_BUILT:=$(PKG_BUILD_DIR)/.built
STAMP_INSTALLED:=$(PKG_BUILD_DIR)/.pkg_installed
STAGING_DIR_HOST:=$(TOPDIR)/staging_dir/host
HOST_STAMP_INSTALLED:=$(STAGING_DIR_HOST)/stamp/.$(PKG_NAME)_installed
PACKAGE_DIR:=$(BIN_DIR)/packages
PACKAGE_BIN:=$(PKG_NAME)-$(PKGARCH)-$(PKG_RELEASE)
PACKAGE_BIN_DPKG:=$(PACKAGE_BIN).deb
STAGING_DIR:=$(PKG_BUILD_DIR)/$(PACKAGE_BIN)
include $(INCLUDE_DIR)/package-dpkg.mk

define Build/Compile/Default
	+$(MAKE_VARS) \
	$(MAKE) $(PKG_JOBS) -C $(PKG_BUILD_DIR)/$(MAKE_PATH) \
		$(MAKE_FLAGS) \
		$(1);
endef
define BuildPackage
  $(eval $(Package/$(1)))  
  .PHONY : clean compile
  define BuildPackage
  endef
  $(call Build/DefaultTargets,$(1))
endef

define Build/DefaultTargets  
  $(eval $(call BuildDPKGVariable,$(1),postinst))
  
  $(STAMP_INSTALLED):
	$(Build/Prepare)
	$(Build/Compile)
	$(call Package/$(PKG_NAME)/install,$(STAGING_DIR))
	$(call Build/InstallDev,$(ROOTFS_DIR))
	$(call BuildTarget/dpkg,$(1))
	touch $$@

  $(HOST_STAMP_INSTALLED):$(STAMP_INSTALLED)
	touch $$@
  compile:$(STAMP_INSTALLED)
  clean:
	rm -rf $(PKG_BUILD_DIR)
  define Build/DefaultTargets
  endef
endef
