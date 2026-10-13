CLANG ?= clang
AR ?= ar
OUT ?= ../../.local/npu-core
PYTHON ?= python3
PAIR_OUT ?= ../../.local/npu-pair

SOURCES := barrier.c admission.c control-v2.c bootstrap.c bootstrap-v2.c cold-setup.c \
	startup.c allocator.c cold-page.c cold-packet.c cold-indication.c cold-tx.c cold-descriptor.c cold-tx-buffer.c cold-rx-event.c gdma.c tunnel-header.c tunnel-packet.c
OBJECTS := $(SOURCES:%.c=$(OUT)/%.o)
HEADERS := $(wildcard *.h)
CFLAGS := --target=riscv32 -march=rv32imac_zicsr -mabi=ilp32 -std=c11 \
	-Os -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-stack-protector

.PHONY: all clean pair pair-check
all: $(OUT)/libw1700k-npu.a

pair:
	cd ../.. && $(PYTHON) tools/build_npu_pair.py --output "$(abspath $(PAIR_OUT))"

pair-check:
	cd ../.. && $(PYTHON) tests/npu/test_npu_image.py --pair "$(abspath $(PAIR_OUT))" -v

$(OUT):
	mkdir -p $@

$(OUT)/%.o: %.c $(HEADERS) | $(OUT)
	$(CLANG) $(CFLAGS) -c $< -o $@

$(OUT)/cold-packet.o: cold-page.c

$(OUT)/libw1700k-npu.a: $(OBJECTS)
	$(AR) rcsD $@ $(OBJECTS)

clean:
	rm -f $(OBJECTS) $(OUT)/libw1700k-npu.a
