// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class SeedNpuUartIrq extends GhidraScript {
    public void run() throws Exception {
        if (!currentProgram.getExecutableSHA256().equalsIgnoreCase(
                "e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643"))
            throw new IllegalStateException("Firmware identity changed");
        Address start = toAddr(0x840047a0L);
        byte[] expected = {(byte)0xb7, 7, (byte)0xc1, 0x1e,
                           (byte)0x83, (byte)0xc7, 0x47, 1};
        if (!java.util.Arrays.equals(getBytes(start, expected.length), expected))
            throw new IllegalStateException("UART handler preimage changed");
        // The registration at 0x84004480 passes this code address in a1.
        // Auto-analysis previously mistyped its first instruction as a pointer.
        clearListing(start, toAddr(0x840047d1L));
        disassemble(start);
        Function function = createFunction(start, "analysis_uart_irq_840047a0");
        if (function == null) function = getFunctionAt(start);
        if (function == null) throw new IllegalStateException("UART handler missing");
        println("SEEDED_UART_IRQ " + function.getEntryPoint() + " " + function.getBody());
    }
}
