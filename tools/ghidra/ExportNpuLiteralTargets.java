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

public class ExportNpuLiteralTargets extends GhidraScript {
    private String sha(byte[] data) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
    }
    private String address(Address value) {
        return "0x" + Long.toHexString(value.getOffset());
    }
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 3 || !args[1].matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("CODE-path expected-sha256 new-output-json");
        byte[] raw = Files.readAllBytes(Path.of(args[0]));
        if (!sha(raw).equals(args[1])) throw new IllegalStateException("CODE hash mismatch");
        long base = 0x84000000L, end = base + raw.length;
        byte[] mapped = new byte[raw.length];
        if (currentProgram.getMemory().getBytes(toAddr(base),mapped) != raw.length || !Arrays.equals(raw,mapped))
            throw new IllegalStateException("Mapped full CODE differs after analysis");
        List<Object> functions = new ArrayList<>();
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException("Decompiler open failed");
        try {
            for (long value : new long[] {0x84004212L,0x840064b4L,0x8400651cL}) {
                Function function = getFunctionAt(toAddr(value));
                if (function == null || !function.getName().equals("literal_target_" + Long.toHexString(value)))
                    throw new IllegalStateException("Exact seeded target missing");
                List<Object> ranges = new ArrayList<>(), instructions = new ArrayList<>();
                AddressRangeIterator iterator = function.getBody().getAddressRanges();
                while (iterator.hasNext()) {
                    AddressRange range = iterator.next();
                    long start = range.getMinAddress().getOffset(), stop = range.getMaxAddress().getOffset()+1;
                    if (start < base || stop > end || stop <= start)
                        throw new IllegalStateException("Body outside exact CODE");
                    byte[] bytes = Arrays.copyOfRange(raw,(int)(start-base),(int)(stop-base));
                    ranges.add(Map.of("start",address(range.getMinAddress()),"inclusive_end",address(range.getMaxAddress()),
                        "bytes",bytes.length,"sha256",sha(bytes)));
                }
                int covered = 0;
                InstructionIterator listing = currentProgram.getListing().getInstructions(function.getBody(),true);
                while (listing.hasNext()) {
                    Instruction instruction = listing.next();
                    long offset = instruction.getAddress().getOffset()-base;
                    byte[] bytes = instruction.getBytes();
                    if (offset < 0 || offset+bytes.length > raw.length ||
                            !Arrays.equals(bytes,Arrays.copyOfRange(raw,(int)offset,(int)offset+bytes.length)))
                        throw new IllegalStateException("Instruction raw-byte mismatch");
                    List<String> flows = new ArrayList<>();
                    for (Address target : instruction.getFlows()) flows.add(address(target));
                    Map<String,Object> row = new LinkedHashMap<>();
                    row.put("address",address(instruction.getAddress()));
                    row.put("bytes_hex",HexFormat.of().formatHex(bytes));
                    row.put("assembly",instruction.toString());
                    row.put("flow_type",instruction.getFlowType().toString());
                    row.put("direct_flows",flows);
                    row.put("fallthrough",instruction.getFallThrough() == null ? null : address(instruction.getFallThrough()));
                    instructions.add(row);
                    covered += bytes.length;
                }
                if (covered == 0 || covered != function.getBody().getNumAddresses())
                    throw new IllegalStateException("Function body has undecoded bytes");
                DecompileResults result = decompiler.decompileFunction(function,120,monitor);
                if (!result.decompileCompleted() || result.getDecompiledFunction() == null)
                    throw new IllegalStateException("Target decompilation failed: " + result.getErrorMessage());
                Map<String,Object> row = new LinkedHashMap<>();
                row.put("entry",address(function.getEntryPoint()));
                row.put("analyst_seeded_name",function.getName());
                row.put("body_ranges",ranges);
                row.put("body_bytes",covered);
                row.put("no_return_metadata",function.hasNoReturn());
                row.put("instructions",instructions);
                row.put("pseudocode",result.getDecompiledFunction().getC());
                functions.add(row);
            }
        } finally { decompiler.dispose(); }
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("passed",true);
        result.put("scope","Three seeded Ghidra functions on an exact CODE map;not a stack or runtime proof.");
        result.put("Ghidra_version",Application.getApplicationVersion());
        result.put("language",currentProgram.getLanguageID().toString());
        result.put("imported_ELF_sha256",currentProgram.getExecutableSHA256());
        result.put("mapped_CODE_sha256",args[1]);
        result.put("mapped_CODE_bytes",raw.length);
        result.put("functions",functions);
        result.put("guest_execution",false);
        result.put("hardware",false);
        result.put("complete_stack_bound",false);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(result)+"\n",
            StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);
        println("NPU_LITERAL_TARGET_EXPORT_PASS functions=3 raw_bytes=" + raw.length);
    }
}
