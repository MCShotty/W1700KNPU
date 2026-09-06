// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;

public class SetupStartupCandidateMap extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1 || !currentProgram.getExecutableSHA256().equalsIgnoreCase(args[0]))
            throw new IllegalStateException("Candidate ELF identity mismatch");
        long[][] ranges = {{0x3e900000L, 0x8000L}, {0x1fb30000L, 0x1000L},
                           {0x1ec0c000L, 0x1000L}};
        String[] names = {"CANDIDATE_SHARED_SRAM", "COPY_GDMA_REGISTERS", "MAILBOX_REGISTERS"};
        for (int i = 0; i < ranges.length; i++) {
            MemoryBlock block = currentProgram.getMemory().createUninitializedBlock(names[i],
                currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(ranges[i][0]),
                ranges[i][1], false);
            block.setRead(true);
            block.setWrite(true);
            block.setExecute(false);
            block.setVolatile(true);
        }
        println("STARTUP_CANDIDATE_VOLATILE_MAP_PASS");
    }
}
