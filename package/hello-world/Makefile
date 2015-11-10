INST_LIB_PATH:=usr/lib
INST_BIN_PATH:=bin
PKG_NAME:=hello-world
PKG_RELEASE:=1.01
PKG_BUILD_DIR := $(BUILD_DIR)/$(PKG_NAME)/src

include $(INCLUDE_DIR)/package.mk
define Package/$(PKG_NAME)/description
	core
endef
define Package/$(PKG_NAME)
	SECTION:=utils
	CATEGORY:=Utilities
	TITLE:=$(PKG_NAME) -- KappaIO hello world
	DEPENDS:=+jansson +libpthread +librt +libstdcpp +rsserial
	Maintainer:=Yuming Liang
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) -r ./src/* $(PKG_BUILD_DIR)/   
endef

define Package/$(PKG_NAME)/install
	$(INSTALL_DIR) $(1)/usr/lib
	$(INSTALL_DIR) $(1)/usr/lib/rsserial
	$(INSTALL_DIR) $(1)/usr/lib/rsserial/endpoints
	$(CP) $(PKG_BUILD_DIR)/$(PKG_NAME)*so* $(1)/usr/lib/
	ln -s /usr/lib/$(PKG_NAME).so $(1)/usr/lib/rsserial/endpoints/$(PKG_NAME).so
endef

define Build/Compile
  $(call Build/Compile/Default,processor_family=$(_processor_family_) BOARD=$(BOARD))
endef

define Build/InstallDev

endef
define Package/$(PKG_NAME)/postinst
#!/bin/sh
# check if we are on real system
#if [ -z "$${IPKG_INSTROOT}" ]; then
echo "Restarting rsserial..."
service rsserial-watch restart
#fi
exit 0
endef

define Package/$(PKG_NAME)/UploadAndInstall
ifeq ($(OPENWRT_BUILD),1)
compile: $(STAGING_DIR_ROOT)/stamp/.$(PKG_NAME)_installed
	$(SCP) $$(PACKAGE_DIR)/$$(PKG_NAME)_$$(VERSION)_$$(ARCH_PACKAGES).ipk $(1):/tmp
	$(SSH) $(1) opkg install --force-overwrite /tmp/$(PKG_NAME)_$$(VERSION)_$$(ARCH_PACKAGES).ipk
	$(SSH) $(1) rm /tmp/$$(PKG_NAME)_$$(VERSION)_$$(ARCH_PACKAGES).ipk
	$(SSH) $(1) rm /tmp/widget_registry.json
endif
ifeq ($(RASPBERRYPI_BUILD),1)
compile:$(STAMP_INSTALLED)
	@echo "---------------------------------------------------"
	@echo "**************** RASPBERRYPI_BUILD ****************"
	@echo "---------------------------------------------------"
	$(SCP) $$(PACKAGE_DIR)/$$(PACKAGE_BIN_DPKG) $(1):/tmp
	$(SSH) $(1) dpkg -i /tmp/$$(PACKAGE_BIN_DPKG)
endif
endef
UPLOAD_PATH:=$(or $(PKG_DST), $($(PKG_NAME)_DST))
$(if $(UPLOAD_PATH), $(eval $(call Package/$(PKG_NAME)/UploadAndInstall, $(UPLOAD_PATH))))

$(eval $(call BuildPackage,$(PKG_NAME)))

