// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class SeedNpuMailboxCallbacks extends GhidraScript {
    private void seed(long address, long end, String name, byte[] expected) throws Exception {
        Address start = toAddr(address);
        if (!java.util.Arrays.equals(getBytes(start, expected.length), expected))
            throw new IllegalStateException("Mailbox callback preimage changed: " + start);
        clearListing(start, toAddr(end));
        disassemble(start);
        Function function = createFunction(start, name);
        if (function == null) function = getFunctionAt(start);
        if (function == null) throw new IllegalStateException("Callback missing: " + start);
        println("SEEDED_MAILBOX_CALLBACK " + function.getEntryPoint() + " " + function.getBody());
    }

    public void run() throws Exception {
        if (!currentProgram.getExecutableSHA256().equalsIgnoreCase(
                "e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643"))
            throw new IllegalStateException("Firmware identity changed");
        // Original common mailbox init writes these callback addresses to
        // gp-0x678 and gp-0x67c. Earlier auto-analysis left both as labels.
        seed(0x84003a86L, 0x84003a9bL, "analysis_mailbox_tunnel_84003a86",
             new byte[] {0x1c, 0x41, 0x13, (byte)0x97, 0x27, 0, (byte)0x97, (byte)0xc7});
        seed(0x84003a9cL, 0x84003c27L, "analysis_mailbox_wifi_84003a9c",
             new byte[] {(byte)0xb7, 7, 0, 0x40, 0x13, (byte)0x87, (byte)0xf7, (byte)0xff});
    }
}
