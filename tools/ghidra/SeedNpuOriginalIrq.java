// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

public class SeedNpuOriginalIrq extends GhidraScript {
    public void run() throws Exception {
        for (long value : new long[] {0x840048f4L,0x84003200L,0x8400326aL}) {
            Address address = toAddr(value);
            Function enclosing = getFunctionContaining(address);
            if (enclosing != null && !enclosing.getEntryPoint().equals(address))
                throw new IllegalStateException("Target lies inside another function: " + address);
            if (getInstructionAt(address) == null && !disassemble(address))
                throw new IllegalStateException("Cannot disassemble target: " + address);
            Function function = getFunctionAt(address);
            if (function == null) function = createFunction(address,"original_irq_" + Long.toHexString(value));
            if (function == null || !function.getEntryPoint().equals(address))
                throw new IllegalStateException("Missing exact function: " + address);
            function.setName("original_irq_" + Long.toHexString(value),SourceType.USER_DEFINED);
            println("NPU_ORIGINAL_IRQ_SEED target=" + address + " no_return=" + function.hasNoReturn());
        }
        println("NPU_ORIGINAL_IRQ_SEEDS_PASS targets=3");
    }
}
