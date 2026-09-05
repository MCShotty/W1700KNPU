// Export complete small vendor modules or selected current NPU entry points.
// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

public class ExportNpuLifecycle extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) throw new IllegalArgumentException("output-dir all|current");
        Path dir = Path.of(args[0]);
        Files.createDirectories(dir);
        boolean all = args[1].equals("all");
        int total = 0, selected = 0, failed = 0;
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Open program failed");
        try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(
                dir.resolve(currentProgram.getName() + ".txt"), StandardCharsets.UTF_8))) {
            out.println("program=" + currentProgram.getName());
            out.println("executable_sha256=" + currentProgram.getExecutableSHA256());
            out.println("language=" + currentProgram.getLanguageID());
            FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext()) {
                monitor.checkCancelled();
                Function function = functions.next();
                MemoryBlock block = currentProgram.getMemory().getBlock(function.getEntryPoint());
                if (function.isExternal() || block == null || !block.isInitialized() ||
                        !block.isExecute() || block.getName().equals("EXTERNAL")) continue;
                total++;
                String name = function.getName();
                if (!all && !name.matches(".*(npu_hw_(init|stop)|npu_device_active|mac_reset_work|mac_restart|dma_reset).*")) continue;
                selected++;
                out.println("\nFUNCTION " + name + " @ " + function.getEntryPoint());
                ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(function.getEntryPoint());
                while (refs.hasNext()) {
                    Reference ref = refs.next();
                    out.println("XREF " + ref.getFromAddress() + " " + ref.getReferenceType());
                }
                DecompileResults result = decompiler.decompileFunction(function, 90, monitor);
                boolean ok = result.decompileCompleted() && result.getDecompiledFunction() != null;
                out.println("decompiled=" + ok);
                if (ok) out.println(result.getDecompiledFunction().getC());
                else { failed++; out.println(result.getErrorMessage()); }
            }
            out.println("\ntotal_defined_functions=" + total);
            out.println("selected_functions=" + selected);
            out.println("failed_decompilations=" + failed);
        } finally { decompiler.dispose(); }
        if (selected == 0 || failed != 0) throw new IllegalStateException("Incomplete lifecycle export");
        println("W1700K_LIFECYCLE_EXPORT_PASS selected=" + selected + " total=" + total);
    }
}
