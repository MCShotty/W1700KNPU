#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

typedef uint32_t u32;
typedef uint16_t u16;
#define BIT(n) (1UL << (n))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))

struct reset_controller_dev { unsigned int nr_resets; };
struct of_phandle_args { u32 args[16]; };
struct regmap {
	u32 words[0x838 / 4];
	u32 address, mask, value;
	int error, reads, writes, read_output;
	bool commit_error;
};

static int regmap_update_bits(struct regmap *map, u32 addr, u32 mask, u32 val)
{
	if (addr >= sizeof(map->words) || addr % 4)
		abort();
	map->writes++;
	map->address = addr;
	map->mask = mask;
	map->value = val;
	/* A failed operation may have changed hardware before reporting failure. */
	if (!map->error || map->commit_error)
		map->words[addr / 4] = (map->words[addr / 4] & ~mask) | (val & mask);
	return map->error;
}

static int regmap_read(struct regmap *map, u32 addr, u32 *val)
{
	if (addr >= sizeof(map->words) || addr % 4)
		abort();
	map->reads++;
	map->address = addr;
	if (!map->error)
		*val = map->words[addr / 4];
	else if (map->read_output)
		*val = map->read_output == 1 ? 0 : UINT32_MAX;
	return map->error;
}

#include "reset-control.inc"

static const char *test_name;
static unsigned int cases;
#define CHECK(c) do { if (!(c)) { \
	fprintf(stderr, "FAIL[%s] line %d: %s\n", test_name, __LINE__, #c); \
	exit(11); } } while (0)

static struct regmap map;
static struct en_rst_data data;

static void setup(const u16 *ids, size_t count, u32 seed)
{
	memset(&map, 0, sizeof(map));
	for (size_t i = 0; i < ARRAY_SIZE(map.words); i++)
		map.words[i] = seed;
	data = (struct en_rst_data) {
		.bank_ofs = en7581_rst_ofs, .idx_map = ids, .map = &map,
		.rcdev = { .nr_resets = count },
	};
}

static unsigned long translate(unsigned int id)
{
	struct of_phandle_args spec = { .args = { id } };
	int result = en7523_reset_xlate(&data.rcdev, &spec);
	CHECK(result >= 0 && result < 3 * RST_NR_PER_BANK);
	CHECK(result == data.idx_map[id]);
	CHECK(!map.reads && !map.writes);
	return result;
}

static void write_case(unsigned int logical, u32 seed, bool asserted,
		       int error, bool commit_error)
{
	unsigned long id = translate(logical);
	u32 addr = en7581_rst_ofs[id / RST_NR_PER_BANK];
	u32 mask = (u32)BIT(id % RST_NR_PER_BANK);
	bool high = asserted != (addr == REG_NP_SCU_PCIC);
	u32 wanted = (seed & ~mask) | (high ? mask : 0);
	int result;

	map.error = error;
	map.commit_error = commit_error;
	result = asserted ? en7523_reset_assert(&data.rcdev, id) :
			    en7523_reset_deassert(&data.rcdev, id);
	CHECK(result == error);
	CHECK(map.writes == 1 && !map.reads);
	CHECK(map.address == addr && map.mask == mask);
	CHECK(map.value == (high ? mask : 0));
	for (size_t i = 0; i < ARRAY_SIZE(map.words); i++)
		CHECK(map.words[i] == (i == addr / 4 && (!error || commit_error) ? wanted : seed));
	if (!error) {
		CHECK(en7523_reset_status(&data.rcdev, id) == asserted);
		CHECK(map.reads == 1 && map.writes == 1 && map.address == addr);
	}
	cases++;
}

static void read_case(unsigned int logical, u32 seed, int error, int output)
{
	unsigned long id = translate(logical);
	u32 addr = en7581_rst_ofs[id / RST_NR_PER_BANK];
	bool high = !!(seed & BIT(id % RST_NR_PER_BANK));

	map.error = error;
	map.read_output = output;
	CHECK(en7523_reset_status(&data.rcdev, id) ==
	      (error ? error : high != (addr == REG_NP_SCU_PCIC)));
	CHECK(map.reads == 1 && !map.writes && map.address == addr);
	for (size_t i = 0; i < ARRAY_SIZE(map.words); i++)
		CHECK(map.words[i] == seed);
	cases++;
}

static void counterexample(const char *name)
{
	test_name = name;
	setup(en7581_rst_map, ARRAY_SIZE(en7581_rst_map), 0);
	if (!strcmp(name, "write-error"))
		write_case(EN7581_NPU_RST, 0, true, -EIO, false);
	else if (!strcmp(name, "read-error"))
		read_case(EN7581_NPU_RST, 0, -ETIMEDOUT, 2);
	else if (!strcmp(name, "value-init"))
		write_case(EN7581_NPU_RST, 0, false, 0, false);
	else if (!strcmp(name, "value-pcic"))
		write_case(EN7581_PCIC_PERSTOUT0_RST, 0, true, 0, false);
	else
		abort();
}

int main(int argc, char **argv)
{
	const struct { const u16 *ids; size_t count; } variants[] = {
		{ en7523_rst_map, ARRAY_SIZE(en7523_rst_map) },
		{ en7581_rst_map, ARRAY_SIZE(en7581_rst_map) },
		{ an7583_rst_map, ARRAY_SIZE(an7583_rst_map) },
	};
	const int errors[] = { -EIO, -ETIMEDOUT, -EAGAIN };
	u32 seeds[68] = { 0, UINT32_MAX, 0xaaaaaaaa, 0x55555555 };
	unsigned int resets = 0, nominal, writes, reads;

	if (argc == 2) {
		counterexample(argv[1]);
		printf("{\"case\":\"%s\",\"passed\":true}\n", argv[1]);
		return 0;
	}
	CHECK(argc == 1);
	for (unsigned int i = 0; i < 32; i++) {
		seeds[4 + i * 2] = (u32)BIT(i);
		seeds[5 + i * 2] = ~(u32)BIT(i);
	}
	test_name = "nominal";
	for (size_t v = 0; v < ARRAY_SIZE(variants); v++) {
		resets += variants[v].count;
		for (unsigned int id = 0; id < variants[v].count; id++)
			for (size_t s = 0; s < ARRAY_SIZE(seeds); s++)
				for (int a = 0; a <= 1; a++) {
					setup(variants[v].ids, variants[v].count, seeds[s]);
					write_case(id, seeds[s], a, 0, false);
				}
	}
	nominal = cases;
	test_name = "write-error";
	for (size_t v = 0; v < ARRAY_SIZE(variants); v++)
		for (unsigned int id = 0; id < variants[v].count; id++)
			for (size_t e = 0; e < ARRAY_SIZE(errors); e++)
				for (int a = 0; a <= 1; a++)
					for (int side = 0; side <= 1; side++) {
						setup(variants[v].ids, variants[v].count, 0x55555555);
						write_case(id, 0x55555555, a, errors[e], side);
					}
	writes = cases - nominal;
	test_name = "read-error";
	for (size_t v = 0; v < ARRAY_SIZE(variants); v++)
		for (unsigned int id = 0; id < variants[v].count; id++)
			for (size_t e = 0; e < ARRAY_SIZE(errors); e++)
				for (int output = 0; output <= 2; output++) {
					setup(variants[v].ids, variants[v].count, 0xaaaaaaaa);
					read_case(id, 0xaaaaaaaa, errors[e], output);
				}
	reads = cases - nominal - writes;
	test_name = "translation";
	for (size_t v = 0; v < ARRAY_SIZE(variants); v++) {
		const u32 invalid[] = { variants[v].count, variants[v].count + 1, UINT32_MAX };
		setup(variants[v].ids, variants[v].count, 0);
		for (size_t i = 0; i < ARRAY_SIZE(invalid); i++) {
			struct of_phandle_args spec = { .args = { invalid[i] } };
			CHECK(en7523_reset_xlate(&data.rcdev, &spec) == -EINVAL);
			CHECK(!map.reads && !map.writes);
			cases++;
		}
	}
	printf("{\"cases\":%u,\"mapped_resets\":%u,\"variants\":3,"
	       "\"nominal\":%u,\"write_faults\":%u,\"read_faults\":%u,"
	       "\"translation_rejections\":9}\n", cases, resets, nominal, writes, reads);
	return 0;
}
