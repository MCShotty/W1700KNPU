// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

public class SeedNpuLiteralTargets extends GhidraScript {
    public void run() throws Exception {
        for (long value : new long[] {0x84004212L,0x840064b4L,0x8400651cL}) {
            Address address = toAddr(value);
            if (getInstructionAt(address) == null && !disassemble(address))
                throw new IllegalStateException("Cannot disassemble literal target " + address);
            Function function = getFunctionAt(address);
            String name = "literal_target_" + Long.toHexString(value);
            if (function == null) function = createFunction(address,name);
            if (function == null || !function.getEntryPoint().equals(address))
                throw new IllegalStateException("Missing exact target function " + address);
            function.setName(name,SourceType.USER_DEFINED);
        }
        println("NPU_LITERAL_TARGET_SEEDS_PASS targets=3");
    }
}
