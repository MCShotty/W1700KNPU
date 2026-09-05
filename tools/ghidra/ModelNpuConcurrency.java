// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;

public class ModelNpuConcurrency extends GhidraScript {
    public void run() throws Exception {
        if (!currentProgram.getExecutableSHA256().equalsIgnoreCase(
                "e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643"))
            throw new IllegalStateException("Firmware identity changed");
        // Independent harts observe these globals even when this function does not.
        for (String name : new String[] {"NPU_SRAM_INIT", "NPU_SRAM_BSS"}) {
            MemoryBlock block = currentProgram.getMemory().getBlock(name);
            if (block == null) throw new IllegalStateException("Missing shared SRAM mapping");
            block.setVolatile(true);
        }
        // Verified permanent worker loops, not inferred from a function name.
        long[] workers = {0x8400cdc6L, 0x8400cb0eL, 0x8400cd1aL, 0x8400d0aeL,
                          0x8400e3fcL, 0x8400ec48L, 0x8400c9b0L, 0x84000aeeL};
        for (long value : workers) {
            Address start = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
            Function function = getFunctionAt(start);
            if (function == null) {
                disassemble(start);
                function = createFunction(start, String.format("worker_%08x", value));
            }
            if (function == null) throw new IllegalStateException("Cannot seed worker " + start);
            InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
            while (instructions.hasNext()) {
                Instruction instruction = instructions.next();
                if (instruction.getFlowType().isTerminal() &&
                        (instruction.getMnemonicString().equals("ret") || instruction.toString().equals("c.jr ra")))
                    throw new IllegalStateException("Unexpected worker return at " + instruction.getAddress());
            }
            function.setNoReturn(true);
            println("CONCURRENT_WORKER_NORETURN " + start + " " + function.getName());
        }
        println("CONCURRENT_SRAM_VOLATILE_PASS");
    }
}
