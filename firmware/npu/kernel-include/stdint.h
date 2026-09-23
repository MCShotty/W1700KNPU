#ifndef W1700K_NPU_KERNEL_STDINT_H
#define W1700K_NPU_KERNEL_STDINT_H

#ifndef __KERNEL__
#error "This include path is only for the kernel-bound control client"
#endif

#include <linux/types.h>
#include <linux/limits.h>

#define UINT32_MAX U32_MAX

#endif
