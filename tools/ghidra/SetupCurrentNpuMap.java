// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.listing.Function;
import java.io.FileInputStream;
import java.nio.file.Files;
import java.nio.file.Path;

public class SetupCurrentNpuMap extends GhidraScript {
    private Address at(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }
    private void tail(String name, long base, long length, boolean vol) throws Exception {
        if (length <= 0) return;
        MemoryBlock block = currentProgram.getMemory().createUninitializedBlock(name, at(base), length, false);
        block.setRead(true); block.setWrite(true); block.setExecute(false); block.setVolatile(vol);
    }
    private void data(String name, long base, Path file, boolean vol) throws Exception {
        try (FileInputStream input = new FileInputStream(file.toFile())) {
            MemoryBlock block = currentProgram.getMemory().createInitializedBlock(name, at(base), input, Files.size(file), monitor, false);
            block.setRead(true); block.setWrite(true); block.setExecute(false); block.setVolatile(vol);
        }
    }
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("companion-data-file");
        Path companion = Path.of(args[0]);
        byte[] bytes = Files.readAllBytes(companion);
        long base = 0x84000000L;
        MemoryBlock code = currentProgram.getMemory().getBlock(at(base));
        if (code == null || bytes.length == 0 || bytes.length >= 0x40000) throw new IllegalStateException("Unexpected input mapping");
        long end = code.getEnd().getOffset() + 1;
        // Hash-gated boundary: the final CLZ helper ends at 0x8401a2e8;
        // jump tables and strings follow, not executable functions.
        long textEnd = 0x8401a2e8L;
        currentProgram.getMemory().split(code, at(textEnd));
        MemoryBlock rodata = currentProgram.getMemory().getBlock(at(textEnd));
        rodata.setName("NPU_RODATA");
        rodata.setRead(true); rodata.setWrite(false); rodata.setExecute(false);
        code.setRead(true); code.setWrite(false); code.setExecute(true);
        tail("NPU_CODE_RESERVED", end, 0x84200000L - end, false);
        data("NPU_SRAM_INIT", 0x3e900000L, companion, false);
        tail("NPU_SRAM_BSS", 0x3e900000L + bytes.length, 0x40000 - bytes.length, false);
        data("NPU_PHYSICAL_INIT", 0x1e900000L, companion, true);
        tail("NPU_MMIO", 0x1e900000L + bytes.length, 0x1ec13000L - 0x1e900000L - bytes.length, true);
        tail("NPU_RING_SRAM", 0x3e800000L, 0x100000L, true);
        tail("NPU_COPY_DMA", 0x1fb30000L, 0x1000L, true);
        disassemble(at(base));
        if (getFunctionAt(at(base)) == null) createFunction(at(base), "rv32_reset");
        currentProgram.getSymbolTable().addExternalEntryPoint(at(base));
        int count = 0;
        for (int off = 0; off + 4 <= bytes.length; off += 4) {
            long target = (bytes[off] & 255L) | ((bytes[off + 1] & 255L) << 8) |
                          ((bytes[off + 2] & 255L) << 16) | ((bytes[off + 3] & 255L) << 24);
            if (target < base || target >= textEnd || (target & 1) != 0) continue;
            disassemble(at(target));
            Function function = getFunctionAt(at(target));
            if (function == null && getFunctionContaining(at(target)) == null)
                createFunction(at(target), String.format("npu_table_%03x", off));
            count++;
        }
        println("CURRENT_NPU_MAP code_end=" + Long.toHexString(end) + " data=" + bytes.length + " pointers=" + count);
    }
}
