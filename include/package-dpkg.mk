define shvar
V_$(subst .,_,$(subst -,_,$(subst /,_,$(1))))
endef
define shexport
$(call shvar,$(1))=$$(call $(1))
export $(call shvar,$(1))
endef

define BuildDPKGVariable
ifdef Package/$(1)/$(2)
  $(call shexport,Package/$(1)/$(2))
  $(1)_COMMANDS += var2file "$(call shvar,Package/$(1)/$(2))" $(2);
endif
endef

define PKG_template
IPKG_$(1):=$(PACKAGE_DIR)/$(2)_$(3)_$(4).ipk
IDIR_$(1):=$(PKG_BUILD_DIR)/ipkg/$(2)
INFO_$(1):=$(IPKG_STATE_DIR)/info/$(2).list
DPKG_$(1):=$(PACKAGE_DIR)/$(2)_$(3)_$(4).deb
endef

define BuildTarget/dpkg
	mkdir -p $(PACKAGE_DIR)
	$(INSTALL_DIR) $(STAGING_DIR)/DEBIAN
	( \
		echo "Package: $(1)"; \
		echo "Maintainer: $(Maintainer)"; \
		echo "Version: $(PKG_RELEASE)"; \
		DEPENDS='$(EXTRA_DEPENDS)'; \
		$(if $(MAINTAINER),echo "Maintainer: $(MAINTAINER)"; ) \
		echo "Architecture: $(PKGARCH)"; \
		echo "Installed-Size: 0"; \
		echo -n "Description: \n core"; $(SH_FUNC) getvar $(call shvar,Package/$(1)/description) | sed -e 's,^[[:space:]]*, ,g'; \
	) > $(STAGING_DIR)/DEBIAN/control
	chmod 755 $(STAGING_DIR)/DEBIAN/control
	$(SH_FUNC) (cd $(STAGING_DIR)/DEBIAN; \
		$($(1)_COMMANDS) \
	)
	chmod 755 $(STAGING_DIR)/DEBIAN/postinst
	dpkg-deb --build $(STAGING_DIR) $(PACKAGE_DIR)/$(PACKAGE_BIN_DPKG)
	chmod 755 $(PACKAGE_DIR)/$(PACKAGE_BIN_DPKG)
endef