/* Host execution of extracted driver C; page-pool/DMA/NAPI are explicit models. */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint16_t __le16;
typedef uint64_t dma_addr_t;
typedef int spinlock_t;
#define __packed __attribute__((packed))
#define __aligned(n) __attribute__((aligned(n)))
#define __iomem
#define BIT(n) (1U << (n))
#define GENMASK(h, l) ((~0U >> (31 - (h))) & (~0U << (l)))
#define FIELD_GET(mask, value) (((value) & (mask)) >> __builtin_ctz(mask))
#define FIELD_PREP(mask, value) (((u32)(value) << __builtin_ctz(mask)) & (mask))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define max_t(t, a, b) ((t)(a) > (t)(b) ? (t)(a) : (t)(b))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define SKB_DATA_ALIGN(n) (((n) + 63U) & ~(size_t)63U)
#define SKB_WITH_OVERHEAD(n) ((n) - SKB_DATA_ALIGN(sizeof(struct skb_shared_info)))

struct page { unsigned char data[8192]; };
struct frag { struct page *page; int off, len; };
struct skb_shared_info { int nr_frags; struct frag frags[MAX_SKB_FRAGS]; };
struct sk_buff {
	void *data;
	unsigned int len, head_len, capacity;
	bool live, recycle;
	struct skb_shared_info shared;
};
#include "rx-definitions.inc"

struct mt76_dev;
struct napi_struct { struct mt76_dev *dev; };
struct airoha_npu { int present; };
struct driver_ops {
	void (*rx_skb)(struct mt76_dev *, enum mt76_rxq_id, struct sk_buff *, u32 *);
	void (*rx_poll_complete)(struct mt76_dev *, enum mt76_rxq_id);
};
struct mt76_dev {
	void *dma_dev;
	struct { struct airoha_npu *npu; } mmio;
	struct mt76_queue q_rx[__MT_RXQ_MAX];
	struct napi_struct napi[__MT_RXQ_MAX];
	struct driver_ops *drv;
};

enum owner { UNUSED, RING, SKB, RELEASED };
struct buffer { void *data; enum owner owner; unsigned int releases; };
static struct page pages[512];
static struct buffer buffers[1024];
static struct sk_buff skbs[64];
static struct mt76_dev dev;
static struct airoha_npu npu;
static struct mt76_queue_entry entries[512];
static struct airoha_npu_rx_dma_desc descriptors[512];
static u32 pending_info[512];
static bool pending[512];
static int next_buffer, next_skb, pool_limit, build_fail;
static int alloc_calls, build_calls, syncs, releases, duplicate_release;
static int use_after_release, bounds, q_writes, delivered, completions, rx_completions;
static int barriers, last_ctrl, rcu_depth, locks;
static int reads[512][2];
static enum mt76_rxq_id active_qid;
static bool after, mutate_on_build;
static unsigned int checks, cases;
static int partial_cases, valid_cases, malformed_cases, invalid_cases;

static void check(bool ok, const char *why)
{
	checks++;
	if (!ok) { fprintf(stderr, "oracle:%s case=%u\n", why, cases); exit(3); }
}

static struct buffer *buffer_for(void *data)
{
	for (int i = 0; i < next_buffer; i++)
		if (buffers[i].data == data)
			return &buffers[i];
	check(false, "unknown-buffer");
	return NULL;
}

static struct page *virt_to_head_page(void *data)
{
	uintptr_t value = (uintptr_t)data;
	for (size_t i = 0; i < ARRAY_SIZE(pages); i++)
		if (value >= (uintptr_t)pages[i].data && value < (uintptr_t)(pages[i].data + sizeof(pages[i].data)))
			return &pages[i];
	check(false, "unknown-page");
	return NULL;
}

static void *page_address(struct page *page) { return page->data; }
static dma_addr_t page_pool_get_dma_addr(struct page *page)
{
	return 0x10000000U + (page - pages) * sizeof(page->data);
}
static int page_pool_get_dma_dir(void *pool) { return 2; }
static void *mt76_get_page_pool_buf(struct mt76_queue *q, int *offset, int size)
{
	alloc_calls++;
	if (pool_limit == 0) return NULL;
	if (pool_limit > 0) pool_limit--;
	check(next_buffer < (int)ARRAY_SIZE(buffers), "model-buffer-capacity");
	*offset = (next_buffer % 2) * 4096 + 64;
	void *data = pages[next_buffer / 2].data + *offset;
	buffers[next_buffer++] = (struct buffer){ .data = data, .owner = RING };
	return data;
}

static void release_buffer(void *data)
{
	struct buffer *b = buffer_for(data);
	if (b->releases++) duplicate_release++;
	b->owner = RELEASED;
	releases++;
}
static void mt76_put_page_pool_buf(void *data, bool direct) { release_buffer(data); }
static void dma_sync_single_for_cpu(void *device, dma_addr_t address, unsigned int len, int direction)
{
	syncs++;
	check(direction == 2, "dma-direction");
	check(len > 0 && len <= 1800, "dma-sync-bounds");
}
static void spin_lock_bh(spinlock_t *lock) { check(locks++ == 0, "nested-lock"); }
static void spin_unlock_bh(spinlock_t *lock) { check(--locks == 0, "unlock"); }
static void rcu_read_lock(void) { rcu_depth++; }
static void rcu_read_unlock(void) { check(--rcu_depth == 0, "rcu-balance"); }
#define rcu_dereference(p) (p)
#define mt76_priv(p) (p)
#define Q_WRITE(q, field, value) do { q_writes++; check((value) == (q)->tail, "tail-doorbell"); } while (0)

static u32 observe_read(const u32 *p)
{
	for (int i = 0; i < (int)ARRAY_SIZE(descriptors); i++) {
		if (p == &descriptors[i].ctrl) { reads[i][0]++; last_ctrl = i; }
		if (p == &descriptors[i].info) reads[i][1]++;
	}
	return *p;
}
#define READ_ONCE(value) observe_read(&(value))
static void dma_rmb(void)
{
	barriers++;
	if (last_ctrl >= 0 && pending[last_ctrl]) {
		descriptors[last_ctrl].info = pending_info[last_ctrl];
		pending[last_ctrl] = false;
	}
}

static struct sk_buff *napi_build_skb(void *data, unsigned int size)
{
	build_calls++;
	if (build_fail) { build_fail--; return NULL; }
	struct buffer *b = buffer_for(data);
	if (b->owner == RELEASED) use_after_release++;
	b->owner = SKB;
	check(next_skb < (int)ARRAY_SIZE(skbs), "model-skb-capacity");
	struct sk_buff *skb = &skbs[next_skb++];
	*skb = (struct sk_buff){ .data = data, .capacity = SKB_WITH_OVERHEAD(size), .live = true };
	if (mutate_on_build) {
		for (int i = 0; i < (int)ARRAY_SIZE(descriptors); i++) {
			descriptors[i].ctrl = NPU_RX_DMA_DESC_DONE_MASK |
				FIELD_PREP(NPU_RX_DMA_DESC_CUR_LEN_MASK, 4095);
			descriptors[i].info ^= 0x456;
		}
	}
	return skb;
}
static void __skb_put(struct sk_buff *skb, unsigned int len)
{
	if (len > skb->capacity) bounds++;
	skb->len += len;
	skb->head_len = len;
}
static void skb_reset_mac_header(struct sk_buff *skb) { }
static void skb_mark_for_recycle(struct sk_buff *skb) { skb->recycle = true; }
static struct skb_shared_info *skb_shinfo(struct sk_buff *skb) { return &skb->shared; }
static void skb_add_rx_frag(struct sk_buff *skb, int i, struct page *page, int off, int len, unsigned int size)
{
	check(i >= 0 && i < MAX_SKB_FRAGS, "fragment-capacity");
	struct buffer *b = buffer_for(page->data + off);
	if (b->owner == RELEASED) use_after_release++;
	b->owner = SKB;
	if ((unsigned int)len > SKB_WITH_OVERHEAD(size)) bounds++;
	skb->shared.frags[i] = (struct frag){ page, off, len };
	skb->shared.nr_frags = i + 1;
	skb->len += len;
}
static void dev_kfree_skb(struct sk_buff *skb)
{
	if (!skb) return;
	check(!IS_ERR(skb) && skb->live && skb->recycle, "skb-free-state");
	release_buffer(skb->data);
	for (int i = 0; i < skb->shared.nr_frags; i++) {
		struct frag *f = &skb->shared.frags[i];
		release_buffer(f->page->data + f->off);
	}
	skb->live = false;
}
static bool napi_complete(struct napi_struct *napi) { completions++; return true; }
static void mt76_rx_poll_complete(struct mt76_dev *d, enum mt76_rxq_id qid, struct napi_struct *napi)
{
	rx_completions++;
}
static void rx_skb(struct mt76_dev *d, enum mt76_rxq_id qid, struct sk_buff *skb, u32 *info)
{
	check(!IS_ERR(skb), "drop-not-delivered");
	delivered++;
	dev_kfree_skb(skb);
}
static void rx_poll_complete(struct mt76_dev *d, enum mt76_rxq_id qid) { }
static struct driver_ops driver = { rx_skb, rx_poll_complete };

#include "rx-driver.inc"

static struct mt76_queue *setup(int size, int tail)
{
	memset(&dev, 0, sizeof(dev));
	memset(entries, 0, sizeof(entries));
	memset(descriptors, 0, sizeof(descriptors));
	memset(buffers, 0, sizeof(buffers));
	memset(skbs, 0, sizeof(skbs));
	memset(reads, 0, sizeof(reads));
	memset(pending, 0, sizeof(pending));
	next_buffer = next_skb = build_fail = 0;
	alloc_calls = build_calls = syncs = releases = duplicate_release = use_after_release = bounds = 0;
	q_writes = delivered = completions = rx_completions = barriers = rcu_depth = locks = 0;
	last_ctrl = -1; pool_limit = -1; mutate_on_build = false;
	dev.mmio.npu = &npu; dev.drv = &driver;
	struct mt76_queue *q = &dev.q_rx[active_qid];
	*q = (struct mt76_queue){ .entry = entries, .desc = (void *)descriptors,
		.ndesc = size, .tail = tail, .head = tail,
		.buf_size = 1800 + SKB_DATA_ALIGN(sizeof(struct skb_shared_info)) };
	dev.napi[active_qid].dev = &dev;
	check(mt76_npu_fill_rx_queue(&dev, q) == size - 1, "initial-fill");
	return q;
}

static u32 packet(struct mt76_queue *q, int count)
{
	int frames = count ? count : 1;
	u32 last = 0;
	for (int i = 0; i < frames; i++) {
		int index = (q->tail + i) % q->ndesc;
		descriptors[index].ctrl = NPU_RX_DMA_DESC_DONE_MASK |
			FIELD_PREP(NPU_RX_DMA_DESC_CUR_LEN_MASK, 64 + i);
		last = descriptors[index].info = 0x12300U + i;
		if (!i) last = descriptors[index].info |= FIELD_PREP(NPU_RX_DMA_PKT_COUNT_MASK, count);
	}
	return last;
}

static void cleanup(struct mt76_queue *q, bool clean)
{
	mt76_npu_queue_cleanup(&dev, q);
	check(q->queued == 0 && locks == 0, "cleanup-count");
	if (clean) {
		check(!duplicate_release && !use_after_release, "single-release");
		for (int i = 0; i < next_buffer; i++)
			check(buffers[i].owner == RELEASED && buffers[i].releases == 1, "no-lost-buffer");
	}
}

static void consume_check(struct mt76_queue *q, struct sk_buff *skb, int tail, int frames, u32 info, u32 expected)
{
	check(skb && !IS_ERR(skb), "complete-delivery");
	check(skb->shared.nr_frags == frames - 1, "complete-fragment-count");
	check(skb->data == buffers[0].data && skb->head_len == 64, "head-identity");
	for (int i = 1; i < frames; i++) {
		struct frag *f = &skb->shared.frags[i - 1];
		check(f->page->data + f->off == buffers[i].data && f->len == 64 + i, "fragment-identity");
	}
	check(skb->len == (unsigned int)(64 * frames + frames * (frames - 1) / 2), "packet-length");
	check(info == expected, "packet-info-snapshot");
	check(q->tail == (tail + frames) % q->ndesc && q->queued == q->ndesc - 1 - frames, "queue-consume");
	if (after) {
		for (int i = 0; i < frames; i++)
			check(entries[(tail + i) % q->ndesc].buf == NULL, "consumed-entry-clear");
	}
	dev_kfree_skb(skb);
	cleanup(q, true);
}

static void complete_at(int size, int tail)
{
	for (int count = 0; count <= 15; count++) {
		int frames = count ? count : 1;
		if (frames > MAX_SKB_FRAGS + 1) continue;
		struct mt76_queue *q = setup(size, tail);
		u32 expected = packet(q, count), info = 0;
		struct sk_buff *skb = mt76_npu_dequeue(&dev, q, &info);
		consume_check(q, skb, tail, frames, info, expected);
		cases++; valid_cases++;
	}
}

static void complete_cases(void)
{
	for (int size = 16; size <= 18; size++)
		for (int tail = 0; tail < size; tail++) complete_at(size, tail);
	for (int i = 0; i < 4; i++) complete_at(512, (int[]){0, 1, 510, 511}[i]);
}

static void partial_and_retry(void)
{
	for (int frames = 2; frames <= 15 && frames <= MAX_SKB_FRAGS + 1; frames++) {
		for (int missing = 1; missing < frames; missing++) {
			for (int wrap = 0; wrap < 2; wrap++) {
				int tail = wrap ? 15 : 0;
				struct mt76_queue *q = setup(17, tail);
				u32 expected = packet(q, frames), info = 0;
				int index = (tail + missing) % q->ndesc;
				descriptors[index].ctrl &= ~NPU_RX_DMA_DESC_DONE_MASK;
				struct sk_buff *skb = mt76_npu_dequeue(&dev, q, &info);
				check(!skb && q->tail == tail && q->queued == 16 && !q_writes, "partial-retain");
				if (after) {
					check(!releases && !build_calls && !syncs, "partial-retain");
					descriptors[index].ctrl |= NPU_RX_DMA_DESC_DONE_MASK;
					skb = mt76_npu_dequeue(&dev, q, &info);
					consume_check(q, skb, tail, frames, info, expected);
				} else {
					check(releases == missing, "baseline-prefix-release");
					cleanup(q, false);
					check(duplicate_release == missing, "baseline-cleanup-double-release");
				}
				cases++; partial_cases++;
			}
		}
	}
	for (int frames = 1; frames <= 15 && frames <= MAX_SKB_FRAGS + 1; frames++) {
		struct mt76_queue *q = setup(17, 16);
		u32 expected = packet(q, frames), info = 0;
		build_fail = 1;
		check(!mt76_npu_dequeue(&dev, q, &info), "allocation-failure");
		check(!releases && !q_writes && q->queued == 16 && q->tail == 16, "allocation-retain");
		struct sk_buff *skb = mt76_npu_dequeue(&dev, q, &info);
		consume_check(q, skb, 16, frames, info, expected);
		cases++;
	}
}

static void length_cases(void)
{
	for (int frames = 1; frames <= 15 && frames <= MAX_SKB_FRAGS + 1; frames++) {
		for (int bad = 0; bad < frames; bad++) {
			struct mt76_queue *q = setup(17, 16);
			packet(q, frames);
			int index = (16 + bad) % 17;
			descriptors[index].ctrl = NPU_RX_DMA_DESC_DONE_MASK |
				FIELD_PREP(NPU_RX_DMA_DESC_CUR_LEN_MASK, (bad & 1) ? 16383 : 1801);
			u32 info = 0;
			struct sk_buff *skb = mt76_npu_dequeue(&dev, q, &info);
			if (after) {
				check(IS_ERR(skb) && (intptr_t)skb == -EINVAL, "length-drop");
				check(!bounds && !build_calls && releases == frames && info == 0, "drop-before-skb");
			} else {
				check(skb && !IS_ERR(skb) && bounds == 1, "baseline-length-overflow");
				dev_kfree_skb(skb);
			}
			check(q->queued == 16 - frames, "drop-consume");
			cleanup(q, true);
			cases++; malformed_cases++;
		}
	}
	if (MAX_SKB_FRAGS < 14) {
		struct mt76_queue *q = setup(17, 16);
		packet(q, 15);
		u32 info = 0;
		struct sk_buff *skb = mt76_npu_dequeue(&dev, q, &info);
		if (after) {
			check(IS_ERR(skb) && releases == 15 && !build_calls, "capacity-drop");
			cleanup(q, true);
		} else {
			check(skb->shared.nr_frags == MAX_SKB_FRAGS, "baseline-capacity");
			dev_kfree_skb(skb);
			cleanup(q, false);
			int lost = 0;
			for (int i = 0; i < next_buffer; i++) lost += buffers[i].owner != RELEASED;
			check(lost == 14 - MAX_SKB_FRAGS, "baseline-fragment-leak");
		}
		cases++;
	}
}

static void invalid_host_cases(void)
{
	if (!after) return;
	for (int variant = 0; variant < 14; variant++) {
		struct mt76_queue *q = setup(17, 16), original = *q;
		packet(q, 3);
		struct mt76_queue_entry saved = entries[0];
		switch (variant) {
		case 0: q->queued = 0; break;
		case 1: q->queued = -1; break;
		case 2: q->queued = 18; break;
		case 3: q->ndesc = 0; break;
		case 4: q->ndesc = -1; break;
		case 5: q->tail = 17; break;
		case 6: q->desc = NULL; break;
		case 7: q->entry = NULL; break;
		case 8: q->buf_size = 0; break;
		case 9: q->buf_size = -1; break;
		case 10: q->buf_size = SKB_DATA_ALIGN(sizeof(struct skb_shared_info)); break;
		case 11: entries[0].buf = NULL; break;
		case 12: entries[0].dma_len[0] = 0; break;
		case 13: entries[0].dma_len[0] = 1801; break;
		}
		u32 info = 0;
		check(!mt76_npu_dequeue(&dev, q, &info), "invalid-host-hold");
		check(!build_calls && !releases && !syncs && !q_writes, "invalid-host-no-effects");
		*q = original; entries[0] = saved;
		cleanup(q, true);
		cases++; invalid_cases++;
	}
}

static void metadata_cases(void)
{
	struct mt76_queue *q = setup(17, 16);
	u32 expected = packet(q, 3), info = 0;
	for (int i = 0; i < 3; i++) {
		int index = (16 + i) % 17;
		pending_info[index] = descriptors[index].info;
		descriptors[index].info = 0;
		pending[index] = true;
	}
	struct sk_buff *skb = mt76_npu_dequeue(&dev, q, &info);
	if (after) {
		check(barriers == 3 && skb->shared.nr_frags == 2, "publication-count");
		consume_check(q, skb, 16, 3, info, expected);
	} else {
		check(!barriers && skb->shared.nr_frags == 0, "baseline-unpublished-info");
		dev_kfree_skb(skb); cleanup(q, true);
	}
	cases++;
	q = setup(17, 16); expected = packet(q, 3); info = 0;
	mutate_on_build = true;
	skb = mt76_npu_dequeue(&dev, q, &info);
	if (after) consume_check(q, skb, 16, 3, info, expected);
	else {
		check(bounds == 2 && info != expected, "baseline-metadata-reread");
		dev_kfree_skb(skb); cleanup(q, true);
	}
	cases++;
	q = setup(17, 16); packet(q, 1); info = 0;
	descriptors[16].ctrl &= ~NPU_RX_DMA_DESC_DONE_MASK;
	check(!mt76_npu_dequeue(&dev, q, &info), "first-not-done");
	check(!syncs && !build_calls && !releases, "first-not-done-effects");
	if (after) check(!reads[16][1] && !barriers, "no-unpublished-info-read");
	cleanup(q, true); cases++;
	if (after) {
		q = setup(17, 16); packet(q, 3); q->queued = 2;
		check(!mt76_npu_dequeue(&dev, q, &info) && !build_calls && !syncs, "insufficient-queued");
		q->queued = 16; cleanup(q, true); cases++;
	}
}

static void poll_cases(void)
{
	struct mt76_queue *q = setup(17, 0);
	mt76_npu_queue_cleanup(&dev, q);
	int allocations = alloc_calls;
	check(mt76_npu_rx_poll(&dev.napi[active_qid], 0) == 0, "zero-budget-return");
	if (after) check(alloc_calls == allocations && !completions, "zero-budget-page-pool");
	else check(alloc_calls > allocations, "baseline-zero-budget-refill");
	cleanup(q, true); cases++;
	if (!after) return;
	for (int budget = 1; budget <= 18; budget++) {
		q = setup(17, 0);
		for (int i = 0; i < 16; i++) {
			descriptors[i].ctrl = NPU_RX_DMA_DESC_DONE_MASK |
				FIELD_PREP(NPU_RX_DMA_DESC_CUR_LEN_MASK, 1801);
		}
		int done = mt76_npu_rx_poll(&dev.napi[active_qid], budget);
		check(done == (budget < 16 ? budget : 16), "drop-budget");
		check(!delivered && !rx_completions && !build_calls, "drop-not-delivered");
		check(completions == (budget > 16), "napi-budget-completion");
		check(q->queued == 16, "refill-count");
		cleanup(q, true); cases++;
	}
	q = setup(17, 16); packet(q, 3);
	check(mt76_npu_rx_poll(&dev.napi[active_qid], 1) == 1, "valid-poll-budget");
	check(delivered == 1 && rx_completions == 1 && !completions && q->queued == 16, "valid-poll-delivery");
	cleanup(q, true); cases++;
	q = setup(17, 16); packet(q, 3);
	pool_limit = 0;
	check(mt76_npu_rx_poll(&dev.napi[active_qid], 4) == 1 && q->queued == 13, "refill-allocation-failure");
	cleanup(q, true); cases++;
	q = setup(17, 16); allocations = alloc_calls; dev.mmio.npu = NULL;
	check(mt76_npu_rx_poll(&dev.napi[active_qid], 4) == 0 && alloc_calls == allocations, "detached-poll");
	cleanup(q, true); cases++;
}

static void boundary_cases(void)
{
	for (int length = 0; length <= 1800; length += length == 0 ? 1 : 1799) {
		struct mt76_queue *q = setup(17, 16);
		packet(q, 1);
		descriptors[16].ctrl = NPU_RX_DMA_DESC_DONE_MASK | FIELD_PREP(NPU_RX_DMA_DESC_CUR_LEN_MASK, length);
		u32 info = 0;
		struct sk_buff *skb = mt76_npu_dequeue(&dev, q, &info);
		check(skb && !IS_ERR(skb) && skb->len == (unsigned int)length && !bounds, "length-boundary");
		dev_kfree_skb(skb); cleanup(q, true); cases++;
	}
	struct mt76_queue *q = setup(17, 16);
	packet(q, 3);
	descriptors[16].ctrl = NPU_RX_DMA_DESC_DONE_MASK | FIELD_PREP(NPU_RX_DMA_DESC_CUR_LEN_MASK, 1801);
	descriptors[0].ctrl &= ~NPU_RX_DMA_DESC_DONE_MASK;
	u32 info = 0;
	check(!mt76_npu_dequeue(&dev, q, &info) && !q_writes && q->queued == 16, "malformed-incomplete-hold");
	if (after) check(!releases && !syncs && !build_calls, "malformed-incomplete-no-effects");
	cleanup(q, after); cases++;
	if (after) {
		q = setup(17, 16); packet(q, 1); entries[16].dma_len[0] = 32;
		struct sk_buff *skb = mt76_npu_dequeue(&dev, q, &info);
		check(IS_ERR(skb) && !build_calls && releases == 1, "mapped-length-bound");
		cleanup(q, true); cases++;
	}
	q = setup(17, 16);
	for (int i = 0; i < 24; i++) {
		packet(q, 3);
		check(mt76_npu_rx_poll(&dev.napi[active_qid], 1) == 1, "repeated-poll");
		check(q->queued == 16 && delivered == i + 1, "repeated-refill");
	}
	cleanup(q, true); cases++;
}

int main(int argc, char **argv)
{
	check(argc == 3, "arguments");
	after = !strcmp(argv[1], "after");
	active_qid = !strcmp(argv[2], "npu1") ? MT_RXQ_NPU1 : MT_RXQ_NPU0;
	complete_cases(); partial_and_retry(); length_cases();
	invalid_host_cases(); metadata_cases(); poll_cases(); boundary_cases();
	printf("{\"cases\":%u,\"assertions\":%u,\"valid\":%d,\"partial\":%d,"
	       "\"malformed_lengths\":%d,\"invalid_host\":%d,\"max_skb_frags\":%d,"
	       "\"queue_id\":%d,\"page_pool_dma_napi\":\"models\",\"passed\":true}\n",
	       cases, checks, valid_cases, partial_cases, malformed_cases, invalid_cases, MAX_SKB_FRAGS, active_qid);
	return 0;
}
