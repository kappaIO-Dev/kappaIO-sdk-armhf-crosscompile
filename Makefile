#makefile
export BUILD_DIR:=${CURDIR}/compile
export INSTALL_DIR:=install -d -m0755
export INSTALL_BIN:=install -m0755
export CP:=cp -fpR
export CC:=arm-linux-gnueabihf-gcc
export GCC:=arm-linux-gnueabihf-gcc
export CXX:=arm-linux-gnueabihf-g++
export CC_INCLUDE_DIR:=-I${CURDIR}/rootfs/usr/include/ \
	-I${CURDIR}/rootfs/usr/include/c++/4.8/ \
	-I${CURDIR}/rootfs/usr/include/kappaio
export INCLUDE_DIR:= ${CURDIR}/include
export TOPDIR:=${CURDIR}
export ROOTFS_DIR:=${CURDIR}/rootfs
export LDFLAGS:=--sysroot=${CURDIR}/rootfs \
	-L${ROOTFS_DIR}/usr/lib/arm-linux-gnueabihf \
	-L${ROOTFS_DIR}/lib/arm-linux-gnueabihf \
	-L${ROOTFS_DIR}/usr/lib/kappaio
export PKGARCH:=armhf
export RASPBERRYPI_BUILD:=1
export BIN_DIR:=${CURDIR}/bin
export SCP:=scp
export SSH:=ssh
export PATH:=${PATH}:${CURDIR}/tools/arm-bcm2708/gcc-linaro-arm-linux-gnueabihf-raspbian-x64/bin

$(foreach subdir,$(shell find package -mindepth 1 -maxdepth 1 -type d), $(info $(subdir)))

define subtargets
  $(1)/compile:
	$(MAKE) -C $(1) compile
  $(1)/clean:
	$(MAKE) -C $(1) clean
endef
$(foreach subdir,$(shell find package -mindepth 1 -maxdepth 1 -type d), $(eval $(call subtargets, $(subdir))))
