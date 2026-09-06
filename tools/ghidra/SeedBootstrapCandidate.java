// @category W1700K
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.SourceType;
import java.util.ArrayList;

public class SeedBootstrapCandidate extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 4 || (args.length - 1) % 3 != 0 ||
            !currentProgram.getExecutableSHA256().equalsIgnoreCase(args[0]))
            throw new IllegalStateException("Bootstrap identity/seed arguments mismatch");
        for (int i = 1; i < args.length; i += 3) {
            String name = args[i];
            Address start = toAddr(Long.parseUnsignedLong(args[i+1], 16));
            Address end = toAddr(Long.parseUnsignedLong(args[i+2], 16));
            if (!name.matches("npu_[a-z0-9_]+") || start.getOffset() < 0x84040000L ||
                end.getOffset() >= 0x84048000L || start.compareTo(end) >= 0)
                throw new IllegalStateException("Invalid bootstrap function span");
            ArrayList<Address> remove = new ArrayList<>();
            FunctionIterator all = currentProgram.getFunctionManager().getFunctions(true);
            while (all.hasNext()) {
                Address entry = all.next().getEntryPoint();
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
            if (!cursor.equals(end.add(1))) throw new IllegalStateException("Span ends inside instruction");
            Function function = getFunctionAt(start);
            AddressSet body = new AddressSet(start, end);
            if (function == null)
                currentProgram.getFunctionManager().createFunction(name, start, body, SourceType.USER_DEFINED);
            else {
                function.setName(name, SourceType.USER_DEFINED);
                function.setBody(body);
            }
            println("BOOTSTRAP_SEEDED " + name + " " + start + " " + end);
        }
    }
}
