include $(TOPDIR)/rules.mk

PKG_NAME:=w1700k-system-defaults
PKG_VERSION:=2026.09.04
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/w1700k-system-defaults
  SECTION:=base
  CATEGORY:=Base system
  TITLE:=Conservative W1700K service defaults
  DEPENDS:=@TARGET_airoha_an7581 +adblock +softethervpn5-server
endef

define Package/w1700k-system-defaults/description
Profile-only first-boot defaults for adblock maintenance and SoftEther startup.
SoftEther remains installed but disabled until explicitly enabled by the user.
endef

define Build/Compile
endef

define Package/w1700k-system-defaults/install
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/99-w1700k-system-defaults $(1)/etc/uci-defaults/
endef

$(eval $(call BuildPackage,w1700k-system-defaults))
