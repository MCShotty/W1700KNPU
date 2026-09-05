// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import java.nio.file.Files;
import java.nio.file.Path;

public class SeedResetTargets extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("targets-tsv");
        int selected = 0;
        for (String line : Files.readAllLines(Path.of(args[0]))) {
            String[] fields = line.split("\t", -1);
            if (fields.length != 10 || !fields[1].endsWith("/" + currentProgram.getName())) continue;
            if (!fields[2].equalsIgnoreCase(currentProgram.getExecutableSHA256()))
                throw new IllegalStateException("Target input SHA256 mismatch");
            MemoryBlock block = currentProgram.getMemory().getBlock(fields[3]);
            if (block == null || !block.isInitialized() || !block.isExecute())
                throw new IllegalStateException("Missing executable section " + fields[3]);
            long offset = Long.decode(fields[4]);
            long end = Long.decode(fields[5]);
            if (offset < 0 || end <= offset || end > block.getSize())
                throw new IllegalStateException("Target outside section");
            Address start = block.getStart().add(offset);
            Function function = getFunctionAt(start);
            if (function == null) {
                disassemble(start);
                function = createFunction(start, "analysis_reset_" + fields[3].replace('.', '_') +
                                          "_" + Long.toHexString(offset));
            }
            if (function == null) throw new IllegalStateException("Cannot seed " + start);
            println("RESET_SEED " + fields[3] + "+" + fields[4] + " @ " + start +
                    " name=" + function.getName() + " evidence=" + fields[8]);
            selected++;
        }
        if (selected == 0) throw new IllegalStateException("No input-bound reset targets");
    }
}
