/* Actual parser and radiotap C with explicit skb/framework dependencies. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

typedef uint8_t u8;
typedef int8_t s8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef u16 __le16;
typedef u32 __le32;
typedef u16 __be16;
typedef u32 __be32;
#define __packed __attribute__((packed))
#define __aligned(n) __attribute__((aligned(n)))
#define __attribute_const__ __attribute__((const))
#define __always_inline inline
#define BIT(n) (1UL << (n))
#define BIT_ULL(n) (1ULL << (n))
#define GENMASK(h, l) ((~0UL >> (63 - (h))) & (~0UL << (l)))
#define FIELD_GET(m, v) (((v) & (m)) >> __builtin_ctzl(m))
#define FIELD_PREP(m, v) (((unsigned long)(v) << __builtin_ctzl(m)) & (m))
#define cpu_to_le16(x) ((u16)(x))
#define cpu_to_le32(x) ((u32)(x))
#define le16_to_cpu(x) ((u16)(x))
#define le32_to_cpu(x) ((u32)(x))
#define cpu_to_be16(x) ((u16)__builtin_bswap16(x))
#define be16_to_cpu(x) ((u16)__builtin_bswap16(x))
#define le32_get_bits(x, m) FIELD_GET(m, le32_to_cpu(x))
#define le16_get_bits(x, m) FIELD_GET(m, le16_to_cpu(x))
#define le32_encode_bits(x, m) cpu_to_le32(FIELD_PREP(m, x))
#define le16_encode_bits(x, m) cpu_to_le16(FIELD_PREP(m, x))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define unlikely(x) (x)
#define likely(x) (x)
#define fallthrough __attribute__((fallthrough))
#define max_t(t, a, b) ((t)(a) > (t)(b) ? (t)(a) : (t)(b))
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define struct_group(name, ...) __VA_ARGS__
#define BUILD_BUG_ON(x) _Static_assert(!(x), "build-bug")
#define EXPORT_SYMBOL_GPL(x)
#define ETH_ALEN 6
#define ETH_HLEN 14
#define VLAN_HLEN 4
#define ETH_P_8021Q 0x8100
#define ETH_P_AARP 0x80f3
#define ETH_P_IPX 0x8137
#define ETH_P_802_3_MIN 0x0600
#define CHECKSUM_UNNECESSARY 1
#define IEEE80211_MAX_CHAINS 4
static u16 get_unaligned_le16(const void *p) { u16 v; memcpy(&v, p, 2); return v; }
static u32 get_unaligned_le32(const void *p) { u32 v; memcpy(&v, p, 4); return v; }
static u16 get_unaligned_be16(const void *p) { return __builtin_bswap16(get_unaligned_le16(p)); }
static unsigned int assertions, packets, dropped, received, pull_calls, copies;
static int fail_pull, active_case;
static int active_queue;
static void check(bool valid, const char *name)
{
	assertions++;
	if (!valid) { fprintf(stderr, "oracle:%s case=%d\n", name, active_case); exit(3); }
}
#define WARN_ONCE(condition, ...) (check(!(condition), "warn"), (condition))

struct sk_buff {
	u8 *storage, *data, *frags;
	unsigned int len, head_len, data_len, allocation;
	unsigned int mac_offset;
	int ip_summed;
	bool freed;
	u8 cb[128] __aligned(8);
};
struct ethhdr { u8 h_dest[6], h_source[6]; __be16 h_proto; } __packed;
struct mt76_wcid { int link_id; };
struct mt7996_vif { int dummy; };
struct ieee80211_bss_conf { u8 bssid[6]; };
struct ieee80211_sta { u8 addr[6]; };
struct ieee80211_vif {
	u8 addr[6];
	struct ieee80211_bss_conf *link_conf[16];
	struct mt7996_vif drv_priv;
};
struct mt7996_sta { struct mt7996_vif *vif; };
struct mt7996_sta_link { struct mt76_wcid wcid; struct mt7996_sta *sta; };
struct ieee80211_channel { int center_freq, band; };
struct ieee80211_supported_band { void *channels; };
struct mt76_phy {
	u8 band_idx, antenna_mask;
	unsigned long state;
	void *priv;
	struct { struct ieee80211_channel *chan; } chandef;
	struct { struct ieee80211_supported_band sband; } sband_2g, sband_5g, sband_6g;
};
struct mt76_queue { int dummy; };
struct mt76_dev {
	struct mt76_phy phy, *phys[3];
	struct mt76_queue q_rx[32];
	struct { int wed_hif2; } mmio;
};
struct mt7996_phy { u32 rx_ampdu_ts, ampdu_ref; };
struct mt7996_dev { struct mt76_dev mt76; struct mt7996_phy phy; };
static struct mt7996_dev device;
static struct ieee80211_channel channel;
static struct ieee80211_sta station;
static struct ieee80211_vif vif;
static struct ieee80211_bss_conf link;
static struct mt7996_sta msta;
static struct mt7996_sta_link msta_link;
static bool have_station;
static const u8 bridge_tunnel_header[6] = {0xaa, 0xaa, 3, 0, 0, 0xf8};
static const u8 rfc1042_header[6] = {0xaa, 0xaa, 3, 0, 0, 0};
#define rcu_dereference(p) (p)
static void ether_addr_copy(void *d, const void *s) { memcpy(d, s, ETH_ALEN); }
static bool test_bit(int bit, const unsigned long *v) { return (*v & BIT(bit)) != 0; }
static struct ieee80211_sta *wcid_to_sta(struct mt76_wcid *wcid) { return &station; }
static struct mt76_wcid *mt7996_rx_get_wcid(struct mt7996_dev *d, u16 idx, u8 band)
{
	return have_station ? &msta_link.wcid : NULL;
}
static bool mt7996_band_valid(struct mt7996_dev *d, int band) { return band < 3; }
static void mt76_wcid_add_poll(struct mt76_dev *d, struct mt76_wcid *wcid) { }
static int mt76_get_rate(struct mt76_dev *d, void *sband, int i, bool cck) { return i; }

static bool pskb_may_pull(struct sk_buff *skb, unsigned int len)
{
	pull_calls++;
	if (len > skb->len) return false;
	if (len <= skb->head_len) return true;
	if (fail_pull > 0 && --fail_pull == 0) return false;
	unsigned int old_room = skb->data - skb->storage;
	unsigned int take = len - skb->head_len;
	u8 *replacement = malloc(old_room + len);
	check(replacement != NULL, "allocation");
	memcpy(replacement, skb->storage, old_room + skb->head_len);
	memcpy(replacement + old_room + skb->head_len, skb->frags, take);
	memmove(skb->frags, skb->frags + take, skb->data_len - take);
	free(skb->storage);
	skb->storage = replacement; skb->data = replacement + old_room;
	skb->allocation = old_room + len; skb->head_len = len; skb->data_len -= take;
	copies++;
	return true;
}
static void *skb_pull(struct sk_buff *skb, unsigned int len)
{
	if (len > skb->len) return NULL;
	check(len <= skb->head_len, "pull-nonlinear");
	skb->data += len; skb->head_len -= len; skb->len -= len;
	return skb->data;
}
static void *skb_push(struct sk_buff *skb, unsigned int len)
{
	check(len <= (unsigned int)(skb->data - skb->storage), "push-headroom");
	skb->data -= len; skb->head_len += len; skb->len += len;
	return skb->data;
}
#define __skb_push skb_push
static void skb_set_mac_header(struct sk_buff *skb, int off)
{
	skb->mac_offset = skb->data - skb->storage + off;
}
static void *skb_mac_header(struct sk_buff *skb) { return skb->storage + skb->mac_offset; }
static void dev_kfree_skb(struct sk_buff *skb) { check(!skb->freed, "duplicate-skb-free"); skb->freed = true; dropped++; }
static void napi_consume_skb(struct sk_buff *skb, int n) { dev_kfree_skb(skb); }
static bool mtk_wed_device_active(void *p) { return false; }
static void mt7996_mac_tx_free(struct mt7996_dev *d, void *p, int len) { }
static void mt7996_mac_add_txs(struct mt7996_dev *d, void *p) { }
static void mt7996_debugfs_rx_fw_monitor(struct mt7996_dev *d, void *p, int len) { }
static void mt7996_mcu_rx_event(struct mt7996_dev *d, struct sk_buff *skb) { received++; skb->freed = true; }
static void mt76_rx(struct mt76_dev *d, int qid, struct sk_buff *skb) { received++; }
static void mt76_rx_beacon(struct mt76_phy *phy, struct sk_buff *skb) { }
static void mt7996_wed_check_ppe(struct mt7996_dev *d, struct mt76_queue *q, struct mt7996_sta *sta, struct sk_buff *skb, u32 info) { }
static void mt76_npu_check_ppe(struct mt76_dev *d, struct sk_buff *skb, u32 info) { }

#include "parser-definitions.inc"
#include "parser-functions.inc"

static void setup(void)
{
	memset(&device, 0, sizeof(device));
	channel = (struct ieee80211_channel){ .center_freq = 5180, .band = NL80211_BAND_5GHZ };
	device.mt76.phy = (struct mt76_phy){ .state = BIT(MT76_STATE_RUNNING), .antenna_mask = 3,
		.priv = &device.phy, .chandef.chan = &channel, .sband_5g.sband.channels = &channel };
	for (int i = 0; i < 3; i++) device.mt76.phys[i] = &device.mt76.phy;
	vif.link_conf[0] = &link; msta.vif = &vif.drv_priv; msta_link.sta = &msta;
	have_station = true; fail_pull = 0; received = dropped = pull_calls = copies = 0;
}

static struct sk_buff make_skb(const u8 *data, unsigned int len, unsigned int head)
{
	check(head <= len, "input-head");
	struct sk_buff skb = {.len = len, .head_len = head, .data_len = len - head, .allocation = head};
	skb.storage = malloc(head ? head : 1); skb.data = skb.storage;
	skb.frags = malloc(len - head ? len - head : 1);
	memcpy(skb.data, data, head); memcpy(skb.frags, data + head, len - head);
	memset(skb.cb, 0, sizeof(skb.cb));
	return skb;
}
static void destroy(struct sk_buff *skb) { free(skb->storage); free(skb->frags); }

static u32 flags_for_groups(int groups)
{
	const u32 masks[] = {MT_RXD1_NORMAL_GROUP_1, MT_RXD1_NORMAL_GROUP_2,
		MT_RXD1_NORMAL_GROUP_3, MT_RXD1_NORMAL_GROUP_4, MT_RXD1_NORMAL_GROUP_5};
	u32 flags = 0;
	for (int i = 0; i < 5; i++) if (groups & (1 << i)) flags |= masks[i];
	return flags;
}
static void store32(u8 *p, u32 v) { memcpy(p, &v, 4); }
static void store16(u8 *p, u16 v) { memcpy(p, &v, 2); }

struct fixture { unsigned int len, required, offset; int rxv; u8 bytes[768]; };
static struct fixture normal_packet(int groups, int padding, int format, int mode)
{
	struct fixture f = {.rxv = -1};
	u16 frame[] = {IEEE80211_FTYPE_DATA, IEEE80211_FTYPE_DATA | IEEE80211_STYPE_QOS_DATA,
		IEEE80211_FTYPE_DATA | IEEE80211_STYPE_QOS_DATA | IEEE80211_FCTL_TODS | IEEE80211_FCTL_FROMDS | IEEE80211_FCTL_ORDER,
		IEEE80211_FTYPE_MGMT | IEEE80211_STYPE_BEACON,
		IEEE80211_FTYPE_CTL | IEEE80211_STYPE_ACK, IEEE80211_FTYPE_CTL | IEEE80211_STYPE_RTS};
	u16 fc = frame[format % 6];
	bool translated = format >= 6 && format <= 8;
	bool amsdu = format == 9;
	bool ccmp = format == 10;
	if (format == 8) fc = IEEE80211_FTYPE_DATA | IEEE80211_STYPE_QOS_DATA | IEEE80211_FCTL_MOREFRAGS;
	u32 rxd1 = flags_for_groups(groups);
	u32 rxd2 = FIELD_PREP(MT_RXD2_NORMAL_HDR_OFFSET, padding) | MT_RXD2_NORMAL_NON_AMPDU;
	if (translated) rxd2 |= MT_RXD2_NORMAL_HDR_TRANS;
	if (format == 7) rxd2 |= MT_RXD2_NORMAL_HDR_TRANS_ERROR;
	if (ccmp) rxd2 |= FIELD_PREP(MT_RXD2_NORMAL_SEC_MODE, MT_CIPHER_AES_CCMP) | MT_RXD2_NORMAL_FRAG;
	store32(f.bytes, FIELD_PREP(MT_RXD0_PKT_TYPE, PKT_TYPE_NORMAL));
	store32(f.bytes + 4, rxd1); store32(f.bytes + 8, rxd2);
	store32(f.bytes + 12, FIELD_PREP(MT_RXD3_NORMAL_ADDR_TYPE, MT_RXD3_NORMAL_U2M));
	if (amsdu) store32(f.bytes + 16, FIELD_PREP(MT_RXD4_NORMAL_PAYLOAD_FORMAT, MT_RXD4_FIRST_AMSDU_FRAME));
	unsigned int p = 32;
	if (groups & 8) {
		store32(f.bytes + p, FIELD_PREP(MT_RXD8_FRAME_CONTROL, fc));
		store32(f.bytes + p + 8, FIELD_PREP(MT_RXD10_SEQ_CTRL, 0x120));
		p += 16;
	}
	if (groups & 1) { for (int i = 0; i < 16; i++) f.bytes[p + i] = 0x20 + i; p += 16; }
	if (groups & 2) { store32(f.bytes + p, 0x12345678); p += 16; }
	if (groups & 4) {
		f.rxv = p;
		store32(f.bytes + p, FIELD_PREP(MT_PRXV_TX_RATE, 4));
		store32(f.bytes + p + 8, FIELD_PREP(MT_PRXV_TX_MODE, mode));
		store32(f.bytes + p + 12, 0xa0a0a0a0);
		p += 16;
		if (groups & 16) {
			for (int i = 0; i < 24; i++) store32(f.bytes + p + i * 4, 0xabc03412U + i * 0x01020103U);
			p += 96;
		}
	}
	p += 2 * padding; f.offset = p;
	unsigned int header = translated ? (format == 7 ? 20 : 14) : ieee80211_hdrlen(fc);
	if (translated) {
		for (int i = 0; i < 12; i++) f.bytes[p + i] = 0x40 + i;
		store16(f.bytes + p + 12, cpu_to_be16(format == 7 ? ETH_P_8021Q : 0x0800));
		if (format == 7) store16(f.bytes + p + 18, cpu_to_be16(0x0800));
	} else {
		store16(f.bytes + p, fc);
		if (header >= 24) store16(f.bytes + p + 22, 0x120);
	}
	f.required = p + header + (amsdu ? 2 : 0);
	f.len = f.required + 96;
	for (unsigned int i = f.required; i < f.len; i++) f.bytes[i] = (i * 19) ^ 0xa5;
	return f;
}

static u64 digest = 1469598103934665603ULL;
static void hash_byte(u8 b) { digest = (digest ^ b) * 1099511628211ULL; }
static void hash_word(u32 value) { for (int i = 0; i < 4; i++) hash_byte(value >> (8 * i)); }
static void record_packet(struct sk_buff *skb)
{
	struct mt76_rx_status *s = (void *)skb->cb;
	hash_word(skb->len); hash_word(s->flag); hash_word(s->encoding); hash_word(s->bw);
	hash_word(s->seqno); hash_word(s->qos_ctl); hash_word(s->rate_idx); hash_word(s->nss);
	for (unsigned int i = 0; i < skb->head_len; i++) hash_byte(skb->data[i]);
	for (unsigned int i = 0; i < skb->data_len; i++) hash_byte(skb->frags[i]);
}
static void dispatch(struct sk_buff *skb)
{
	u32 info = 0;
	mt7996_queue_rx_skb(&device.mt76, active_queue, skb, &info);
	check(received + dropped == 1, "packet-consumed-once");
}

static void verify_radiotap(struct sk_buff *skb, const struct fixture *f, int mode)
{
	if (f->rxv < 0) return;
	struct mt76_rx_status *s = (void *)skb->cb;
	if (s->flag & RX_FLAG_8023) return;
	u32 rxd1 = get_unaligned_le32(f->bytes + 4);
	if (!(rxd1 & MT_RXD1_NORMAL_GROUP_5)) {
		check(!(s->flag & (RX_FLAG_RADIOTAP_HE | RX_FLAG_RADIOTAP_HE_MU | RX_FLAG_RADIOTAP_TLV_AT_END)), "absent-vector-not-decoded");
		return;
	}
	if (s->encoding != RX_ENC_HE && s->encoding != RX_ENC_EHT) return;
	u8 *mac = skb_mac_header(skb);
	unsigned int prefix = mac - skb->data;
	check(prefix <= skb->head_len, "radiotap-prefix");
	unsigned int payload_head = skb->head_len - prefix;
	struct sk_buff ref = {.len = skb->len - prefix, .head_len = payload_head, .data_len = skb->data_len};
	ref.storage = calloc(1, 256 + payload_head); ref.data = ref.storage + 256;
	ref.frags = malloc(ref.data_len ? ref.data_len : 1);
	memcpy(ref.data, mac, payload_head); memcpy(ref.frags, skb->frags, ref.data_len);
	memcpy(ref.cb, skb->cb, sizeof(ref.cb));
	((struct mt76_rx_status *)ref.cb)->flag &= ~(RX_FLAG_RADIOTAP_HE | RX_FLAG_RADIOTAP_HE_MU | RX_FLAG_RADIOTAP_TLV_AT_END);
	skb_set_mac_header(&ref, 0);
	__le32 vector[28]; memcpy(vector, f->bytes + f->rxv, sizeof(vector));
	if (s->encoding == RX_ENC_HE) mt76_connac3_mac_decode_he_radiotap(&ref, vector, mode);
	else mt76_connac3_mac_decode_eht_radiotap(&ref, vector, mode);
	check(skb->len == ref.len && skb->head_len == ref.head_len && !memcmp(skb->data, ref.data, ref.head_len), "immutable-rxv-radiotap");
	destroy(&ref);
}

static unsigned int nominal(bool fragmented, bool radiotap)
{
	unsigned int count = 0;
	const int modes[] = {MT_PHY_TYPE_HT, MT_PHY_TYPE_HE_SU, MT_PHY_TYPE_HE_MU, MT_PHY_TYPE_HE_TB,
		MT_PHY_TYPE_EHT_SU, MT_PHY_TYPE_EHT_MU};
	for (int groups = 0; groups < 32; groups++) {
		for (int pad = 0; pad <= 7; pad++) {
			for (int format = 0; format <= 10; format++) {
				if (format == 8 && !(groups & 8)) continue;
				if (format == 10 && !(groups & 1)) continue;
				for (int m = 0; m < (radiotap ? (int)ARRAY_SIZE(modes) : 1); m++) {
					struct fixture f = normal_packet(groups, pad, format, modes[m]);
					int heads[] = {0, 1, 3, 4, 31, 32, (int)f.offset - 1, (int)f.required - 1, (int)f.len};
					for (int h = 0; h < (fragmented ? (int)ARRAY_SIZE(heads) : 1); h++) {
						setup(); active_case = count;
						struct sk_buff skb = make_skb(f.bytes, f.len, fragmented ? heads[h] : f.len);
						dispatch(&skb);
						check(received == 1 && !dropped, "normal-received");
						if (fragmented) check(skb.data_len > 0 || heads[h] == (int)f.len, "body-remains-nonlinear");
						if (radiotap) verify_radiotap(&skb, &f, modes[m]);
						record_packet(&skb);
						destroy(&skb); count++;
					}
				}
			}
		}
	}
	return count;
}

static unsigned int truncations(void)
{
	unsigned int count = 0;
	for (int groups = 0; groups < 32; groups++) {
		for (int format = 0; format <= 10; format++) {
			if (format == 8 && !(groups & 8)) continue;
			if (format == 10 && !(groups & 1)) continue;
			struct fixture f = normal_packet(groups, 7, format, MT_PHY_TYPE_HT);
			for (unsigned int len = 0; len < f.required; len++) {
				setup(); active_case = count;
				struct sk_buff skb = make_skb(f.bytes, len, len / 2);
				dispatch(&skb);
				check(!received && dropped == 1, "truncated-header-drop");
				destroy(&skb); count++;
			}
		}
	}
	return count;
}

static unsigned int failures(void)
{
	unsigned int count = 0;
	for (int format = 0; format <= 10; format++) {
		struct fixture f = normal_packet(31, 7, format, MT_PHY_TYPE_HT);
		setup(); struct sk_buff skb = make_skb(f.bytes, f.len, 0); dispatch(&skb);
		unsigned int allocations = copies; destroy(&skb);
		for (unsigned int i = 1; i <= allocations; i++) {
			setup(); fail_pull = i; skb = make_skb(f.bytes, f.len, 0); dispatch(&skb);
			check(!received && dropped == 1, "pull-allocation-drop");
			destroy(&skb); count++;
		}
	}
	setup(); have_station = false;
	struct fixture f = normal_packet(31, 0, 8, MT_PHY_TYPE_HT);
	struct sk_buff skb = make_skb(f.bytes, f.len, 1); dispatch(&skb);
	check(!received && dropped == 1, "unknown-station-drop"); destroy(&skb); count++;
	return count;
}

static unsigned int controls(void)
{
	unsigned int count = 0;
	int types[] = {PKT_TYPE_TXS, PKT_TYPE_RX_EVENT, PKT_TYPE_RX_FW_MONITOR, PKT_TYPE_TXRX_NOTIFY, 31};
	for (size_t t = 0; t < ARRAY_SIZE(types); t++) {
		for (unsigned int len = 4; len <= 96; len++) {
			for (int fragmented = 0; fragmented < 2; fragmented++) {
				u8 data[96] = {0}; store32(data, FIELD_PREP(MT_RXD0_PKT_TYPE, types[t]));
				setup(); struct sk_buff skb = make_skb(data, len, fragmented ? 1 : len);
				dispatch(&skb);
				if (types[t] == PKT_TYPE_RX_EVENT)
					check(received == (len >= sizeof(struct mt7996_mcu_rxd)), "event-header-extent");
				else check(dropped == 1, "control-consumed");
				bool callback_view = types[t] == PKT_TYPE_RX_FW_MONITOR ||
					(types[t] == PKT_TYPE_TXRX_NOTIFY && len >= 12) ||
					(types[t] == PKT_TYPE_RX_EVENT && len >= sizeof(struct mt7996_mcu_rxd)) ||
					(types[t] == PKT_TYPE_TXS && len >= (MT_TXS_HDR_SIZE + MT_TXS_SIZE) * sizeof(__le32));
				if (callback_view) check(skb.head_len == len, "control-linear-view");
				destroy(&skb); count++;
			}
		}
	}
	return count;
}

static unsigned int vector_case(bool missing, bool unknown)
{
	setup();
	struct fixture f = normal_packet(missing ? 4 : 31, 0, unknown ? 8 : 0, MT_PHY_TYPE_EHT_SU);
	have_station = !unknown;
	struct sk_buff skb = make_skb(f.bytes, f.len, f.len); dispatch(&skb);
	if (unknown) check(dropped == 1 && !received, "unknown-station-drop");
	else { check(received == 1, "vector-packet"); verify_radiotap(&skb, &f, MT_PHY_TYPE_EHT_SU); }
	destroy(&skb);
	return 1;
}

int main(int argc, char **argv)
{
	check(argc == 2 || argc == 3, "arguments");
	if (!strcmp(argv[1], "layout")) {
		const u64 values[] = {
#include "probe-values.inc"
		};
		putchar('[');
		for (size_t i = 0; i < ARRAY_SIZE(values); i++)
			printf("%s%llu", i ? "," : "", (unsigned long long)values[i]);
		puts("]");
		return 0;
	}
	active_queue = argc == 3 ? atoi(argv[2]) : MT_RXQ_NPU0;
	unsigned int count = 0;
	if (!strcmp(argv[1], "linear")) count = nominal(false, false);
	else if (!strcmp(argv[1], "fragmented")) count = nominal(true, false);
	else if (!strcmp(argv[1], "radiotap")) count = nominal(true, true);
	else if (!strcmp(argv[1], "truncated")) count = truncations();
	else if (!strcmp(argv[1], "failures")) count = failures();
	else if (!strcmp(argv[1], "controls")) count = controls();
	else if (!strcmp(argv[1], "snapshot")) count = vector_case(false, false);
	else if (!strcmp(argv[1], "missing-vector")) count = vector_case(true, false);
	else if (!strcmp(argv[1], "unknown-station")) count = vector_case(false, true);
	else check(false, "mode");
	printf("{\"mode\":\"%s\",\"queue\":%d,\"cases\":%u,\"assertions\":%u,\"digest\":\"%016llx\"}\n",
	       argv[1], active_queue, count, assertions, (unsigned long long)digest);
	return 0;
}
