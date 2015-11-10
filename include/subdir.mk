ifeq ($(MAKECMDGOALS),prereq)
  SUBTARGETS:=prereq
  PREREQ_ONLY:=1
else
  SUBTARGETS:=clean download prepare compile install update refresh prereq dist distcheck configure
endif

subtarget-default = $(filter-out ., \
	$(if $($(1)/builddirs-$(2)),$($(1)/builddirs-$(2)), \
	$(if $($(1)/builddirs-default),$($(1)/builddirs-default), \
	$($(1)/builddirs))))

define subtarget
  $(call warn_eval,$(1),t,T,$(1)/$(2): $($(1)/) $(foreach bd,$(call subtarget-default,$(1),$(2)),$(1)/$(bd)/$(2)))

endef

define ERROR
	($(call MESSAGE, $(2)); $(if $(BUILD_LOG), echo "$(2)" >> $(BUILD_LOG_DIR)/$(1)/error.txt))
endef

lastdir=$(word $(words $(subst /, ,$(1))),$(subst /, ,$(1)))
diralias=$(if $(findstring $(1),$(call lastdir,$(1))),,$(call lastdir,$(1)))

# Parameters: <subdir>
define subdir
  $(foreach bd,$($(1)/builddirs),
    $(foreach target,$(SUBTARGETS),
      $(foreach btype,$(buildtypes-$(bd)),
        $(if $(call diralias,$(bd)),$(call warn_eval,$(1)/$(bd),l,T,$(1)/$(call diralias,$(bd))/$(btype)/$(target): $(1)/$(bd)/$(btype)/$(target)))
      )
     )
	)
  $(foreach target,$(SUBTARGETS),$(call subtarget,$(1),$(target)))
endef