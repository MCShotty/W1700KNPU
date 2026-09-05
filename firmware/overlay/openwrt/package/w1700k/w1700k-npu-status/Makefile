include $(TOPDIR)/rules.mk

PKG_NAME:=w1700k-npu-status
PKG_VERSION:=2026.09.04
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

OPENWRT_CANDIDATE_COMMIT:=$(shell git -C $(TOPDIR) rev-parse HEAD 2>/dev/null || echo unknown)

include $(INCLUDE_DIR)/package.mk

define Package/w1700k-npu-status
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Read-only W1700K NPU status helpers
  DEPENDS:=@TARGET_airoha_an7581 +uci +jshn
endef

define Package/w1700k-npu-status/description
Read-only, bounded status and capture helpers for the current AN7581 mt76 NPU
implementation. This package installs no service, hotplug rule, sysctl, module
override, UCI default, or policy writer.
endef

define Build/Compile
endef

define Package/w1700k-npu-status/install
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) ./files/usr/sbin/w1700k-wlan-npu-mode $(1)/usr/sbin/
	$(INSTALL_BIN) ./files/usr/sbin/w1700k-wlan-npu-capture $(1)/usr/sbin/
	$(SED) 's,@OPENWRT_CANDIDATE_COMMIT@,$(OPENWRT_CANDIDATE_COMMIT),g' \
		$(1)/usr/sbin/w1700k-wlan-npu-mode
endef

$(eval $(call BuildPackage,w1700k-npu-status))
