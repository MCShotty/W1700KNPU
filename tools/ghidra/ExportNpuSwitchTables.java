// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.framework.Application;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressRangeIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.JumpTable;
import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class ExportNpuSwitchTables extends GhidraScript {
    private String sha(byte[] data) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
    }
    private String address(Address value) {
        if (!value.getAddressSpace().equals(currentProgram.getAddressFactory().getDefaultAddressSpace()))
            throw new IllegalStateException("Non-default address space not supported by this export");
        return "0x" + Long.toHexString(value.getOffset());
    }
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 4 || !args[1].matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("CODE-path expected-sha256 new-output-json target-address...");
        byte[] raw = Files.readAllBytes(Path.of(args[0]));
        if (raw.length == 0 || raw.length > 0x200000 || !sha(raw).equals(args[1]))
            throw new IllegalStateException("CODE identity mismatch");
        long base = 0x84000000L,end = base+raw.length;
        byte[] mapped = new byte[raw.length];
        if (currentProgram.getMemory().getBytes(toAddr(base),mapped) != raw.length || !Arrays.equals(raw,mapped))
            throw new IllegalStateException("Full mapped CODE differs after analysis");
        List<Object> functions = new ArrayList<>();
        DecompInterface decompiler = new DecompInterface();
        decompiler.toggleSyntaxTree(true);
        decompiler.toggleCCode(true);
        if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Decompiler open failed");
        try {
            for (int i=3;i<args.length;i++) {
                if (!args[i].matches("0x[0-9a-f]{8}")) throw new IllegalArgumentException("Invalid target address");
                long value = Long.parseUnsignedLong(args[i].substring(2),16);
                Function function = getFunctionAt(toAddr(value));
                if (function == null) throw new IllegalStateException("No exact function at " + args[i]);
                DecompileResults result = decompiler.decompileFunction(function,120,monitor);
                HighFunction high = result.getHighFunction();
                if (!result.decompileCompleted() || result.getDecompiledFunction() == null || high == null)
                    throw new IllegalStateException("Decompilation failed: " + result.getErrorMessage());
                List<Object> ranges = new ArrayList<>(), instructions = new ArrayList<>(), tables = new ArrayList<>();
                AddressRangeIterator iterator = function.getBody().getAddressRanges();
                while (iterator.hasNext()) {
                    AddressRange range = iterator.next();
                    long start = range.getMinAddress().getOffset(),stop = range.getMaxAddress().getOffset()+1;
                    if (start < base || stop > end || stop <= start) throw new IllegalStateException("Body outside CODE");
                    ranges.add(Map.of("start",address(range.getMinAddress()),"inclusive_end",address(range.getMaxAddress()),
                        "bytes",stop-start,"sha256",sha(Arrays.copyOfRange(raw,(int)(start-base),(int)(stop-base)))));
                }
                InstructionIterator listing = currentProgram.getListing().getInstructions(function.getBody(),true);
                while (listing.hasNext()) {
                    Instruction instruction = listing.next();
                    long offset = instruction.getAddress().getOffset()-base;
                    byte[] bytes = instruction.getBytes();
                    if (offset < 0 || offset+bytes.length > raw.length ||
                            !Arrays.equals(bytes,Arrays.copyOfRange(raw,(int)offset,(int)offset+bytes.length)))
                        throw new IllegalStateException("Instruction raw bytes differ");
                    Map<String,Object> row = new LinkedHashMap<>();
                    row.put("address",address(instruction.getAddress()));
                    row.put("bytes_hex",HexFormat.of().formatHex(bytes));
                    row.put("assembly",instruction.toString());
                    row.put("flow_type",instruction.getFlowType().toString());
                    row.put("fallthrough",instruction.getFallThrough() == null ? null : address(instruction.getFallThrough()));
                    List<String> flows = new ArrayList<>();
                    for (Address flow : instruction.getFlows()) flows.add(address(flow));
                    row.put("flow_targets",flows);
                    instructions.add(row);
                }
                JumpTable[] recovered = high.getJumpTables();
                if (recovered != null) for (JumpTable table : recovered) {
                    Map<String,Object> row = new LinkedHashMap<>();
                    row.put("switch_address",address(table.getSwitchAddress()));
                    List<String> targets = new ArrayList<>();
                    if (table.getCases() != null) for (Address target : table.getCases()) targets.add(address(target));
                    row.put("case_targets",targets);
                    row.put("label_values",table.getLabelValues());
                    List<Object> loads = new ArrayList<>();
                    if (table.getLoadTables() != null) for (JumpTable.LoadTable load : table.getLoadTables()) {
                        Map<String,Object> data = new LinkedHashMap<>();
                        long start = load.getAddress().getOffset();
                        int size = load.getSize(),count = load.getNum();
                        long length = (long)size*count;
                        data.put("address",address(load.getAddress()));
                        data.put("entry_size",size);
                        data.put("entry_count",count);
                        boolean inside = size>0 && count>0 && length<=0x100000 && start>=base && start+length<=end;
                        data.put("inside_CODE",inside);
                        if (inside) {
                            byte[] bytes = Arrays.copyOfRange(raw,(int)(start-base),(int)(start-base+length));
                            data.put("raw_hex",HexFormat.of().formatHex(bytes));
                            data.put("sha256",sha(bytes));
                        }
                        loads.add(data);
                    }
                    row.put("load_tables",loads);
                    row.put("bounds_or_target_permission_proved",false);
                    tables.add(row);
                }
                Map<String,Object> row = new LinkedHashMap<>();
                row.put("entry",address(function.getEntryPoint()));
                row.put("function_name",function.getName());
                row.put("body_ranges",ranges);
                row.put("instructions",instructions);
                row.put("recovered_tables",tables);
                row.put("pseudocode",result.getDecompiledFunction().getC());
                functions.add(row);
            }
        } finally { decompiler.dispose(); }
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("passed",true);
        result.put("scope","Ghidra switch-table metadata and exact CODE bytes only;not a bounds or permitted-target proof.");
        result.put("Ghidra_version",Application.getApplicationVersion());
        result.put("language",currentProgram.getLanguageID().toString());
        result.put("imported_ELF_sha256",currentProgram.getExecutableSHA256());
        result.put("mapped_CODE_sha256",args[1]);
        result.put("functions",functions);
        result.put("new_edges_qualified",false);
        result.put("guest_execution",false);
        result.put("hardware",false);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(result)+"\n",
            StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);
        println("NPU_SWITCH_METADATA_EXPORT_PASS functions=" + functions.size());
    }
}
