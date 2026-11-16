// Collect bounded function metadata for a reviewed binary.
// @category AIWorkspace

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;

public class AiworkEvidence extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String target = args.length == 0 ? "" : args[0];
        DecompInterface session = new DecompInterface();
        try {
            if (!session.openProgram(currentProgram)) {
                throw new IllegalStateException("Ghidra could not open the program for decompilation");
            }
            int count = 0;
            for (Function function : currentProgram.getFunctionManager().getFunctions(true)) {
                monitor.checkCancelled();
                if (!target.isEmpty() && !target.equals(function.getName())) {
                    continue;
                }
                println("AIWORK_FUNCTION " + function.getEntryPoint() + " " + function.getSignature());
                println("AIWORK_CALLS " + function.getCalledFunctions(monitor).stream()
                    .limit(32).map(Function::getName).sorted().toList());
                if (!target.isEmpty()) {
                    var output = session.decompileFunction(function, 15, monitor);
                    if (!output.decompileCompleted()) {
                        throw new IllegalStateException("Decompilation failed for " + target);
                    }
                    String code = output.getDecompiledFunction().getC();
                    println("AIWORK_DECOMPILE_BEGIN");
                    println(code.substring(0, Math.min(code.length(), 6000)));
                    println("AIWORK_DECOMPILE_END");
                }
                if (++count >= 64) {
                    break;
                }
            }
            if (count == 0 && !target.isEmpty()) {
                throw new IllegalArgumentException("Function not found: " + target);
            }
        } finally {
            session.dispose();
        }
    }
}
