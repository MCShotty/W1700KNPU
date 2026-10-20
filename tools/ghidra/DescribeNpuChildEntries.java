// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.framework.Application;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.listing.Function;
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

public class DescribeNpuChildEntries extends GhidraScript {
    private String sha(byte[] data) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
    }
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 4 || !args[1].matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("CODE expected-sha new-output target...");
        byte[] raw = Files.readAllBytes(Path.of(args[0])), mapped = new byte[raw.length];
        long base = 0x84000000L;
        if (raw.length == 0 || raw.length > 0x200000 || !sha(raw).equals(args[1]) ||
            currentProgram.getMemory().getBytes(toAddr(base),mapped) != raw.length || !Arrays.equals(raw,mapped))
            throw new IllegalStateException("Full CODE mapping/identity mismatch");
        List<Object> rows = new ArrayList<>();
        for (int index=3;index<args.length;index++) {
            if (!args[index].matches("0x[0-9a-f]{8}")) throw new IllegalArgumentException("Invalid address");
            long value = Long.parseUnsignedLong(args[index].substring(2),16);
            if (value < base || value+2 > base+raw.length || value%2 != 0)
                throw new IllegalArgumentException("Target outside CODE");
            Address address = toAddr(value);
            Function exact = getFunctionAt(address), containing = getFunctionContaining(address);
            Map<String,Object> row = new LinkedHashMap<>();
            row.put("target",args[index]);
            row.put("exact_function",exact != null);
            row.put("containing_entry",containing == null ? null : "0x"+Long.toHexString(containing.getEntryPoint().getOffset()));
            row.put("instruction_at_target",getInstructionAt(address) != null);
            row.put("target_prefix_hex",HexFormat.of().formatHex(Arrays.copyOfRange(raw,(int)(value-base),
                (int)Math.min(value-base+24,raw.length))));
            List<Object> ranges = new ArrayList<>();
            if (containing != null) for (AddressRange range : containing.getBody().getAddressRanges()) {
                long start=range.getMinAddress().getOffset(),end=range.getMaxAddress().getOffset()+1;
                if (start < base || end > base+raw.length || end <= start)
                    throw new IllegalStateException("Containing body outside CODE");
                ranges.add(Map.of("start","0x"+Long.toHexString(start),"inclusive_end","0x"+Long.toHexString(end-1),
                    "bytes",end-start,"sha256",sha(Arrays.copyOfRange(raw,(int)(start-base),(int)(end-base)))));
            }
            row.put("containing_body_ranges",ranges);
            row.put("local_frame_or_entry_contract_qualified",false);
            rows.add(row);
        }
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("passed",true);
        result.put("scope","Read-only child entry and containing-body inventory,not entry permission or a stack bound.");
        result.put("Ghidra_version",Application.getApplicationVersion());
        result.put("language",currentProgram.getLanguageID().toString());
        result.put("imported_ELF_sha256",currentProgram.getExecutableSHA256());
        result.put("mapped_CODE_sha256",args[1]);
        result.put("rows",rows);
        result.put("analysis_or_function_creation_requested",false);
        result.put("guest_execution",false);
        result.put("hardware",false);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(result)+"\n",
            StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);
        println("NPU_CHILD_ENTRY_INVENTORY_PASS targets="+rows.size());
    }
}
