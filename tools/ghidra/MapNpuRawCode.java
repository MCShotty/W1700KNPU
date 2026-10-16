// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

/** Add exact paired-CODE gaps around an imported component, never overwrite it. */
public class MapNpuRawCode extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2 || !args[1].matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("raw-CODE-path expected-sha256");
        byte[] raw = Files.readAllBytes(Path.of(args[0]));
        if (raw.length == 0 || raw.length > 0x200000)
            throw new IllegalArgumentException("CODE extent outside the checked image window");
        String digest = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));
        if (!digest.equals(args[1])) throw new IllegalStateException("CODE hash mismatch");
        if (!currentProgram.getLanguageID().toString().equals("RISCV:LE:32:AndeStar_v5"))
            throw new IllegalStateException("Wrong target language");
        long base = 0x84000000L, end = base + raw.length;
        Memory memory = currentProgram.getMemory();
        int matched = 0, gaps = 0;

        // Validate all existing component bytes before changing the analysis map.
        for (MemoryBlock block : memory.getBlocks()) {
            if (!block.getStart().getAddressSpace().equals(currentProgram.getAddressFactory().getDefaultAddressSpace()))
                continue;
            long start = block.getStart().getOffset(), stop = block.getEnd().getOffset() + 1;
            if (stop <= base || start >= end) continue;
            if (start < base || stop > end) throw new IllegalStateException("Partial component overlap");
            byte[] expected = Arrays.copyOfRange(raw, (int)(start - base), (int)(stop - base));
            if (block.isInitialized()) {
                byte[] actual = new byte[expected.length];
                if (memory.getBytes(block.getStart(), actual) != actual.length || !Arrays.equals(actual, expected))
                    throw new IllegalStateException("Imported component bytes disagree with paired CODE: " + block.getName());
            } else {
                for (byte value : expected)
                    if (value != 0) throw new IllegalStateException("Nonzero raw CODE in imported BSS");
            }
            matched += expected.length;
        }
        if (matched == 0) throw new IllegalStateException("No imported component inside paired CODE");

        long cursor = base;
        while (cursor < end) {
            monitor.checkCancelled();
            Address address = toAddr(cursor);
            MemoryBlock block = memory.getBlock(address);
            if (block != null) {
                if (!block.isInitialized()) memory.convertToInitialized(block, (byte)0);
                cursor = block.getEnd().getOffset() + 1;
                continue;
            }
            long stop = end;
            for (MemoryBlock next : memory.getBlocks()) {
                if (next.getStart().getAddressSpace().equals(address.getAddressSpace())) {
                    long start = next.getStart().getOffset();
                    if (start > cursor && start < stop) stop = start;
                }
            }
            int offset = (int)(cursor - base), length = (int)(stop - cursor);
            block = memory.createInitializedBlock(".npu.raw." + gaps++, address,
                new ByteArrayInputStream(raw, offset, length), length, monitor, false);
            block.setRead(true);
            block.setWrite(false);
            block.setExecute(true);
            cursor = stop;
        }
        byte[] actual = new byte[raw.length];
        if (memory.getBytes(toAddr(base), actual) != raw.length || !Arrays.equals(actual, raw))
            throw new IllegalStateException("Full paired-CODE readback mismatch");
        println("NPU_RAW_CODE_MAP_PASS bytes=" + raw.length + " component_bytes=" + matched +
                " gap_blocks=" + gaps + " sha256=" + digest);
    }
}
