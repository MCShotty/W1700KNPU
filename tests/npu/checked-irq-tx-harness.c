/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint64_t dma_addr_t;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define unlikely(x) (x)
#define MT76_RESET 0
#define MT_DRV_TX_ALIGNED4_SKBS 1
#define DMA_TO_DEVICE 1
enum mt76_txq_id { MT_TXQ0 };
struct ieee80211_sta { int unused; };
struct mt76_wcid { int unused; };
struct ieee80211_hw { int unused; };
struct sk_buff { struct sk_buff *prev,*next,*frags; int len; void *data; };
struct ieee80211_tx_status { struct ieee80211_sta *sta; struct sk_buff *skb; };
struct mt76_queue_buf { dma_addr_t addr; int len; };
struct mt76_tx_info { struct sk_buff *skb; struct mt76_queue_buf buf[8]; int nbuf,info; };
struct mt76_txwi_cache { int phy_idx,qid; dma_addr_t dma_addr; };
struct mt76_queue { unsigned int queued,ndesc; };
struct mt76_dev;
struct driver { unsigned int drv_flags,txwi_size; int (*tx_prepare_skb)(struct mt76_dev *,u8 *,int,struct mt76_wcid *,struct ieee80211_sta *,struct mt76_tx_info *); };
struct mt76_dev { int rx_lock; void *dma_dev; struct driver *drv; };
struct mt76_phy { struct mt76_dev *dev; unsigned long state; int band_idx; };
static struct mt76_dev dev;
static struct mt76_phy phy;
static struct driver driver;
static struct mt76_txwi_cache cache;
static struct ieee80211_hw hw;
static struct sk_buff skb,fragments[8];
static struct mt76_queue queue;
static bool active,fail_linearize,fail_txwi;
static int admission,prepare_error,map_failure,lock_depth;
static unsigned int admits,linears,gets,txwi_puts,maps,unmaps,prepares,npu_adds,generic_adds,statuses;
static int test_bit(int bit,unsigned long *value) { return !!(*value&(1ul<<bit)); }
static bool mt76_npu_device_active(struct mt76_dev *d) { assert(d==&dev);return active; }
static int mt76_npu_io_admit(struct mt76_dev *d) { assert(d==&dev);admits++;return admission; }
static int skb_linearize(struct sk_buff *s) { assert(s==&skb);linears++;return fail_linearize?-ENOMEM:0; }
static struct mt76_txwi_cache *mt76_get_txwi(struct mt76_dev *d) { assert(d==&dev);gets++;return fail_txwi?NULL:&cache; }
static u8 *mt76_get_txwi_ptr(struct mt76_dev *d,struct mt76_txwi_cache *t) { assert(d==&dev && t==&cache);return (u8 *)&cache; }
static void mt76_insert_hdr_pad(struct sk_buff *s) { assert(s==&skb); }
static int skb_headlen(struct sk_buff *s) { assert(s==&skb);return s->len; }
static dma_addr_t dma_map_single(void *d,void *data,int len,int direction) { assert(d==&dev && len>0 && direction==DMA_TO_DEVICE);return ++maps; }
static int dma_mapping_error(void *d,dma_addr_t addr) { assert(d==&dev);return addr==(unsigned int)map_failure; }
#define skb_walk_frags(s,i) for((i)=(s)->frags;(i);(i)=(i)->next)
static void dma_unmap_single(void *d,dma_addr_t addr,int len,int direction) { assert(d==&dev && len>0 && direction==DMA_TO_DEVICE && addr!=(unsigned int)map_failure);unmaps++; }
static void dma_sync_single_for_cpu(void *d,dma_addr_t addr,int len,int direction) { assert(d==&dev); }
static void dma_sync_single_for_device(void *d,dma_addr_t addr,int len,int direction) { assert(d==&dev); }
static void mt76_put_txwi(struct mt76_dev *d,struct mt76_txwi_cache *t) { assert(d==&dev && t==&cache);txwi_puts++; }
static struct ieee80211_hw *mt76_tx_status_get_hw(struct mt76_dev *d,struct sk_buff *s) { assert(d==&dev && s==&skb);return &hw; }
static void spin_lock_bh(int *lock) { assert(lock==&dev.rx_lock && !lock_depth);lock_depth=1; }
static void spin_unlock_bh(int *lock) { assert(lock==&dev.rx_lock && lock_depth==1);lock_depth=0; }
static void ieee80211_tx_status_ext(struct ieee80211_hw *h,struct ieee80211_tx_status *s) { assert(h==&hw && s->skb==&skb && lock_depth==1);statuses++; }
static int prepare(struct mt76_dev *d,u8 *txwi,int qid,struct mt76_wcid *wcid,struct ieee80211_sta *sta,struct mt76_tx_info *info) { assert(d==&dev && info->nbuf>=2);prepares++;return prepare_error; }
static int mt76_npu_dma_add_buf(struct mt76_phy *p,struct mt76_queue *q,struct sk_buff *s,struct mt76_queue_buf *buf,void *txwi) { assert(p==&phy && q==&queue && s==&skb && prepares==1);npu_adds++;return 7; }
static int mt76_dma_add_buf(struct mt76_dev *d,struct mt76_queue *q,struct mt76_queue_buf *buf,int n,int info,struct sk_buff *s,struct mt76_txwi_cache *t) { assert(d==&dev && q==&queue && s==&skb && prepares==1);generic_adds++;return 8; }

/* ACTUAL_TX */

static void reset(bool enabled) {
    assert(!lock_depth);memset(&dev,0,sizeof(dev));memset(&phy,0,sizeof(phy));memset(&skb,0,sizeof(skb));
    memset(fragments,0,sizeof(fragments));memset(&cache,0,sizeof(cache));
    driver=(struct driver){.txwi_size=32,.tx_prepare_skb=prepare};dev.drv=&driver;dev.dma_dev=&dev;phy.dev=&dev;
    skb.len=100;queue=(struct mt76_queue){.ndesc=32};active=enabled;
    admission=prepare_error=map_failure=0;fail_linearize=fail_txwi=false;
    admits=linears=gets=txwi_puts=maps=unmaps=prepares=npu_adds=generic_adds=statuses=0;
}
static int send(void) { return mt76_dma_tx_queue_skb(&phy,&queue,MT_TXQ0,&skb,NULL,NULL); }
static void failed(int error,unsigned int mapped,unsigned int unmapped,unsigned int prepared) {
    assert(send()==error && maps==mapped && unmaps==unmapped && prepares==prepared);
    assert(statuses==1 && !npu_adds && !generic_adds && !lock_depth);
}
int main(void) {
    unsigned int cases=0;
    for(int enabled=0;enabled<2;enabled++) {
        reset(enabled);assert(send()==(enabled?7:8) && prepares==1 && !statuses && admits==(unsigned int)enabled);cases++;
        reset(enabled);phy.state=1;failed(-ENOMEM,0,0,0);assert(!admits && !gets);cases++;
        reset(enabled);fail_txwi=true;failed(-ENOMEM,0,0,0);assert(gets==1 && !txwi_puts);cases++;
        reset(enabled);map_failure=1;failed(-ENOMEM,1,0,0);assert(txwi_puts==1);cases++;
        reset(enabled);queue.queued=31;failed(-ENOMEM,1,1,0);assert(txwi_puts==1);cases++;
        reset(enabled);prepare_error=-EPROTO;failed(-EPROTO,1,1,1);assert(txwi_puts==1);cases++;
        reset(enabled);skb.frags=&fragments[0];fragments[0].len=50;map_failure=2;
        failed(-ENOMEM,2,1,0);assert(txwi_puts==1);cases++;
    }
    reset(true);fail_linearize=true;failed(-ENOMEM,0,0,0);assert(admits==1 && linears==1 && !gets);cases++;
    const int errors[]={-EIO,-ETIMEDOUT,-ESHUTDOWN};
    for(unsigned int e=0;e<ARRAY_SIZE(errors);e++) {
        reset(true);admission=errors[e];failed(errors[e],0,0,0);
        assert(admits==1 && !linears && !gets && !txwi_puts);cases++;
    }
    printf("{\"passed\":true,\"cases\":%u}\n",cases);
    return 0;
}
