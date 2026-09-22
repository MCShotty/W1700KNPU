/* Original parser/selector/reconfiguration functions with bounded framework models. */
#define _GNU_SOURCE
#define CONFIG_SAE
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ETH_ALEN 6
#define AES_BLOCK_SIZE 16
#define MESH_ENABLED 1
#define MSG_ERROR 1
#define MSG_INFO 2
#define MSG_DEBUG 3
#define os_malloc malloc
#define os_free free
#define os_memcpy memcpy
#define os_memset memset
#define os_memcmp memcmp
#define os_strlen strlen
#define os_strcmp strcmp
#define os_strdup strdup
#define os_strchr strchr
#define os_strstr strstr
#define str_clear_free free
#define wpa_printf(...) ((void)0)
#define wpa_hexdump_ascii(...) ((void)0)
typedef uint8_t u8;
static void *os_zalloc(size_t size) { return calloc(1, size); }

struct sae_pt { int unused; };
struct sae_pk { int unused; };
struct sae_password_entry {
    struct sae_password_entry *next;
    char *password, *identifier;
    u8 peer_addr[ETH_ALEN];
    int vlan_id;
    struct sae_pt *pt;
    const struct sae_pk *pk;
    u8 *success_mac, *fail_mac;
    int num_success_mac, num_fail_mac;
};
struct hostapd_ssid {
    char *wpa_psk_file, *wpa_passphrase;
    u8 ssid[32];
    size_t ssid_len;
    struct sae_pt *pt;
};
struct hostapd_bss_config {
    struct hostapd_ssid ssid;
    struct sae_password_entry *sae_passwords;
    int start_disabled, mesh, sae_track_password, sae_password_psk;
    int *sae_groups;
    void *sae_pw_id_key, *vlan;
    u8 bssid[ETH_ALEN];
};
struct hostapd_config { unsigned int num_bss; struct hostapd_bss_config **bss; };
struct hostapd_data;
struct hostapd_iface { struct hostapd_config *conf; struct hostapd_data **bss; };
struct hostapd_data {
    struct hostapd_iface *iface;
    struct hostapd_bss_config *conf;
    bool started;
    u8 own_addr[ETH_ALEN];
};
struct hostapd_sta_wpa_psk_short {
    struct hostapd_sta_wpa_psk_short *next;
    int is_passphrase;
    char *passphrase;
};
struct sae_tmp { char *dec_pw_id; size_t dec_pw_id_len; uint32_t pw_id_counter; };
struct sae_data { struct sae_tmp *tmp; };
struct sta_info {
    u8 addr[ETH_ALEN];
    int use_sta_psk;
    struct hostapd_sta_wpa_psk_short *psk;
    struct sae_pt *sae_pt;
    struct sae_data *sae;
};

static bool is_broadcast_ether_addr(const u8 *addr)
{
    static const u8 broadcast[ETH_ALEN] = {255, 255, 255, 255, 255, 255};
    return memcmp(addr, broadcast, ETH_ALEN) == 0;
}
static bool ether_addr_equal(const u8 *a, const u8 *b) { return memcmp(a, b, ETH_ALEN) == 0; }
static bool in_mac_addr_list(const u8 *list, int count, const u8 *addr)
{
    for (int i = 0; i < count; i++)
        if (ether_addr_equal(list + i * ETH_ALEN, addr)) return true;
    return false;
}

/* Crypto/PSK derivation is outside these plaintext file/selection scenarios. */
static struct sae_pt *sae_derive_pt(int *groups, const u8 *ssid, size_t len,
                                   const u8 *password, size_t plen, const u8 *id, size_t ilen) { abort(); }
static const void *wpabuf_head(const void *buf) { abort(); }
static size_t wpabuf_len(const void *buf) { abort(); }
static int aes_siv_decrypt(const void *key, ...) { abort(); }
static uint32_t unexpected_be32(const void *buf) { abort(); }
#define WPA_GET_BE32(buf) unexpected_be32(buf)

typedef void uc_vm_t;
typedef struct { int type; const char *text; int64_t number; } uc_value_t;
enum { UC_NULL, UC_STRING, UC_INTEGER, UC_BOOLEAN };
static uc_value_t args[3], result;
static struct hostapd_data live;
static int stops, starts, updates;
#define uc_fn_thisval(type_name) (&live)
#define uc_fn_arg(index) ((index) < nargs ? &args[index] : NULL)
static int ucv_type(uc_value_t *value) { return value ? value->type : UC_NULL; }
static int64_t ucv_int64_get(uc_value_t *value) { return value->number; }
static bool ucv_boolean_get(uc_value_t *value) { return value && value->number != 0; }
static const char *ucv_string_get(uc_value_t *value) { return value->text; }
static uc_value_t *ucv_int64_new(int64_t value) { result.number = value; return &result; }
static struct hostapd_config *read_config(const char *path);
static struct { struct hostapd_config *(*config_read_cb)(const char *); } iface_api = { read_config };
#define interfaces (&iface_api)

static void hostapd_config_free(struct hostapd_config *conf)
{
    if (!conf) return;
    for (unsigned int i = 0; i < conf->num_bss; i++) {
        struct hostapd_bss_config *bss = conf->bss[i];
        struct sae_password_entry *entry = bss->sae_passwords;
        while (entry) {
            struct sae_password_entry *next = entry->next;
            free(entry->password);
            free(entry->identifier);
            free(entry);
            entry = next;
        }
        free(bss->ssid.wpa_psk_file);
        free(bss->ssid.wpa_passphrase);
        free(bss);
    }
    free(conf->bss);
    free(conf);
}
static int bss_reload_vlans(struct hostapd_data *hapd, struct hostapd_bss_config *bss)
{
    assert(!hapd->conf->vlan && !bss->vlan);
    return 0;
}
static void __uc_hostapd_bss_stop(struct hostapd_data *hapd)
{
    if (hapd->started) stops++;
    hapd->started = false;
}
static int __uc_hostapd_bss_start(struct hostapd_data *hapd)
{
    starts++;
    hapd->started = true;
    return 0;
}
static void hostapd_ucode_update_interfaces(void) { updates++; }

#include NATIVE_SNIPPETS

static struct hostapd_config *read_config(const char *path)
{
    struct hostapd_config *conf = calloc(1, sizeof(*conf));
    assert(conf);
    conf->num_bss = 1;
    conf->bss = calloc(1, sizeof(*conf->bss));
    assert(conf->bss);
    conf->bss[0] = calloc(1, sizeof(*conf->bss[0]));
    assert(conf->bss[0]);
    conf->bss[0]->ssid.wpa_psk_file = strdup("new-psk-path");
    conf->bss[0]->ssid.wpa_passphrase = strdup("fallback-passphrase");
    if (parse_sae_password_file(conf->bss[0], path) < 0) {
        hostapd_config_free(conf);
        return NULL;
    }
    return conf;
}

int main(int argc, char **argv)
{
    assert(argc == 6);
    struct hostapd_config *initial = read_config(argv[1]);
    assert(initial);
    free(initial->bss[0]->ssid.wpa_psk_file);
    initial->bss[0]->ssid.wpa_psk_file = strdup("old-psk-path");
    struct hostapd_data *bss_list[] = { &live };
    struct hostapd_iface iface = { .conf = initial, .bss = bss_list };
    live.iface = &iface;
    live.conf = initial->bss[0];
    live.started = true;
    args[0] = (uc_value_t) { .type = UC_STRING, .text = argv[2] };
    args[1] = (uc_value_t) { .type = UC_INTEGER, .number = 0 };
    args[2] = (uc_value_t) { .type = UC_BOOLEAN, .number = atoi(argv[3]) };
    int64_t ret = uc_hostapd_bss_set_config(NULL, args[2].number ? 3 : 2)->number;
    struct sta_info sta = {0};
    assert(hwaddr_aton(argv[4], sta.addr) == 0);
    const u8 *id = strcmp(argv[5], "-") ? (const u8 *) argv[5] : NULL;
    struct sae_password_entry *entry = NULL;
    const char *password = sae_get_password(&live, &sta, id, id ? strlen((const char *)id) : 0,
                                           &entry, NULL, NULL);
    const char *selected = !password ? "none" :
        !strcmp(password, "old-passphrase") ? "old" :
        !strcmp(password, "new-passphrase") ? "new" :
        !strcmp(password, "fallback-passphrase") ? "fallback" : "unexpected";
    int entries = 0;
    for (struct sae_password_entry *p = live.conf->sae_passwords; p; p = p->next) entries++;
    printf("{\"ret\":%lld,\"selected\":\"%s\",\"entries\":%d,\"vlan\":%d,"
           "\"psk_path_new\":%s,\"stops\":%d,\"starts\":%d,\"updates\":%d}\n",
           (long long)ret, selected, entries, entry ? entry->vlan_id : 0,
           !strcmp(live.conf->ssid.wpa_psk_file, "new-psk-path") ? "true" : "false",
           stops, starts, updates);
    hostapd_config_free(iface.conf);
    return 0;
}
