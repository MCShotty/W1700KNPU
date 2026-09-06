// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.SourceType;
import java.util.ArrayList;

public class SeedStartupCandidate extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 5 || !currentProgram.getExecutableSHA256().equalsIgnoreCase(args[0]))
            throw new IllegalStateException("Candidate identity/seed arguments mismatch");
        if (!args[0].equals("16d330eb21f84e47a7bc9f0e5ff49d2c1552cef241455d48770768ded211850a"))
            throw new IllegalStateException("Re-audit symbol spans for a changed ELF");
        String[] names = {"npu_emulation_before_bss", "npu_emulation_cold_start"};
        for (int i = 0; i < 2; i++) {
            Address start = toAddr(Long.parseUnsignedLong(args[1+i*2], 16));
            Address end = toAddr(Long.parseUnsignedLong(args[2+i*2], 16));
            if (start.getOffset() < 0x84040000L || end.getOffset() >= 0x84048000L || start.compareTo(end) >= 0)
                throw new IllegalStateException("Seed outside candidate text");
            ArrayList<Address> remove = new ArrayList<>();
            FunctionIterator all = currentProgram.getFunctionManager().getFunctions(true);
            while (all.hasNext()) {
                Function function = all.next();
                Address entry = function.getEntryPoint();
                if (entry.compareTo(start) > 0 && entry.compareTo(end) <= 0)
                    remove.add(entry);
            }
            for (Address entry : remove) currentProgram.getFunctionManager().removeFunction(entry);
            clearListing(start, end);
            Address cursor = start;
            while (cursor.compareTo(end) <= 0) {
                disassemble(cursor);
                Instruction instruction = getInstructionAt(cursor);
                if (instruction == null) throw new IllegalStateException("Undecoded instruction at " + cursor);
                cursor = cursor.add(instruction.getLength());
            }
            Function function = getFunctionAt(start);
            AddressSet body = new AddressSet(start, end);
            if (function == null)
                function = currentProgram.getFunctionManager().createFunction(names[i], start, body, SourceType.USER_DEFINED);
            else {
                function.setName(names[i], SourceType.USER_DEFINED);
                function.setBody(body);
            }
            println("STARTUP_SEEDED " + names[i] + " " + start + " " + end);
        }
    }
}
