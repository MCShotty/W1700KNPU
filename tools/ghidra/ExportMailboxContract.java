// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Pattern;

public class ExportMailboxContract extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) throw new IllegalArgumentException("output-directory pattern-file");
        Path output = Path.of(args[0]);
        Files.createDirectories(output);
        Pattern selected = Pattern.compile(Files.readString(Path.of(args[1])).trim());
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Program open failed");
        int total = 0, exported = 0, failures = 0;
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
                if (!selected.matcher(function.getName()).matches()) continue;
                exported++;
                out.println("\nFUNCTION " + function.getName() + " @ " + function.getEntryPoint());
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
            out.println("failed_decompilations=" + failures);
        } finally { decompiler.dispose(); }
        if (exported == 0 || failures != 0) throw new IllegalStateException("Contract export incomplete");
        println("MAILBOX_CONTRACT_PASS functions=" + exported + " analyzed=" + total);
    }
}
