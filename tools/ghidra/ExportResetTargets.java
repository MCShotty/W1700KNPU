// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Pattern;

public class ExportResetTargets extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 3) throw new IllegalArgumentException("output-directory targets-tsv pattern-file");
        Path output = Path.of(args[0]);
        Files.createDirectories(output);
        Pattern selected = Pattern.compile(Files.readString(Path.of(args[2])).trim());
        Map<Address, String> targets = new HashMap<>();
        for (String line : Files.readAllLines(Path.of(args[1]))) {
            String[] fields = line.split("\t", -1);
            if (fields.length != 10 || !fields[1].endsWith("/" + currentProgram.getName())) continue;
            if (!fields[2].equalsIgnoreCase(currentProgram.getExecutableSHA256()))
                throw new IllegalStateException("Target input SHA256 mismatch");
            MemoryBlock block = currentProgram.getMemory().getBlock(fields[3]);
            if (block == null) throw new IllegalStateException("Missing target section");
            Address start = block.getStart().add(Long.decode(fields[4]));
            if (getFunctionAt(start) == null) throw new IllegalStateException("Target missing after analysis: " + start);
            targets.put(start, line);
        }
        if (targets.isEmpty()) throw new IllegalStateException("No selected reset targets");
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Program open failed");
        int total = 0, exported = 0, failures = 0, targetCount = 0;
        try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(
                output.resolve(currentProgram.getName() + ".txt"), StandardCharsets.UTF_8))) {
            out.println("program=" + currentProgram.getName());
            out.println("sha256=" + currentProgram.getExecutableSHA256());
            out.println("language=" + currentProgram.getLanguageID());
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext()) {
                monitor.checkCancelled();
                Function function = functions.next();
                MemoryBlock block = currentProgram.getMemory().getBlock(function.getEntryPoint());
                if (function.isExternal() || block == null || !block.isInitialized() ||
                        !block.isExecute() || block.getName().equals("EXTERNAL")) continue;
                total++;
                String target = targets.get(function.getEntryPoint());
                if (target == null && !selected.matcher(function.getName()).matches()) continue;
                exported++;
                if (target != null) targetCount++;
                out.println("\nFUNCTION " + function.getName() + " @ " + function.getEntryPoint());
                out.println("section_relative=" + block.getName() + "+0x" +
                            Long.toHexString(function.getEntryPoint().subtract(block.getStart())));
                if (target != null) out.println("inventory_target=" + target);
                for (Reference reference : getReferencesTo(function.getEntryPoint()))
                    out.println("XREF " + reference.getFromAddress() + " " + reference.getReferenceType());
                DecompileResults result = decompiler.decompileFunction(function, 120, monitor);
                boolean ok = result.decompileCompleted() && result.getDecompiledFunction() != null;
                out.println("decompiled=" + ok);
                if (ok) out.println(result.getDecompiledFunction().getC());
                else { failures++; out.println(result.getErrorMessage()); }
                out.println("ASSEMBLY");
                InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
                while (instructions.hasNext()) {
                    Instruction instruction = instructions.next();
                    out.println(instruction.getAddress() + " " + instruction);
                }
            }
            out.println("\ntotal_executable_functions=" + total);
            out.println("exported_functions=" + exported);
            out.println("inventory_targets_exported=" + targetCount);
            out.println("failed_decompilations=" + failures);
        } finally { decompiler.dispose(); }
        if (targetCount != targets.size() || failures != 0)
            throw new IllegalStateException("Reset export incomplete");
        println("RESET_CONTRACT_PASS functions=" + exported + " targets=" + targetCount + " analyzed=" + total);
    }
}
