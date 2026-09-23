CLANG ?= clang
AR ?= ar
OUT ?= ../../.local/npu-core

SOURCES := barrier.c admission.c control-v2.c bootstrap.c bootstrap-v2.c \
	startup.c allocator.c gdma.c tunnel-header.c tunnel-packet.c
OBJECTS := $(SOURCES:%.c=$(OUT)/%.o)
HEADERS := $(wildcard *.h)
CFLAGS := --target=riscv32 -march=rv32imac_zicsr -mabi=ilp32 -std=c11 \
	-Os -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-stack-protector

.PHONY: all clean
all: $(OUT)/libw1700k-npu.a

$(OUT):
	mkdir -p $@

$(OUT)/%.o: %.c $(HEADERS) | $(OUT)
	$(CLANG) $(CFLAGS) -c $< -o $@

$(OUT)/libw1700k-npu.a: $(OBJECTS)
	$(AR) rcsD $@ $(OBJECTS)

clean:
	rm -f $(OBJECTS) $(OUT)/libw1700k-npu.a
