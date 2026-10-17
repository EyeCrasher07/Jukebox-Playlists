package dev.eyecrasher.jukeboxplaylists;

import java.util.List;
import java.util.Set;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.MethodInsnNode;
import org.objectweb.asm.tree.MethodNode;
import org.objectweb.asm.tree.VarInsnNode;
import org.objectweb.asm.tree.InsnNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

/** LazoDiscs 1.0.7 expects constructor injection absent from Forge 51. */
public final class LazoBootstrapPlugin implements IMixinConfigPlugin {
    @Override public void onLoad(String mixinPackage) {}
    @Override public String getRefMapperConfig() { return null; }
    @Override public boolean shouldApplyMixin(String target, String mixin) { return true; }
    @Override public void acceptTargets(Set<String> ours, Set<String> others) {}
    @Override public List<String> getMixins() { return null; }
    @Override public void preApply(String name, ClassNode target, String mixin, IMixinInfo info) {}

    @Override public void postApply(String name, ClassNode target, String mixin, IMixinInfo info) {
        if (!mixin.endsWith(".LazoBootstrapMixin")) return;
        String context = "net/minecraftforge/fml/javafmlmod/FMLJavaModLoadingContext";
        String signature = "(L" + context + ";)V";
        boolean contextual = false;
        for (MethodNode method : target.methods) {
            if (!method.name.equals("<init>")) continue;
            if (method.desc.equals("()V")) return;
            if (method.desc.equals(signature)) contextual = true;
        }
        if (!contextual) throw new IllegalStateException("Unsupported LazoDiscs Forge 1.21 constructor");
        // Delegate to the original constructor with the same active FML context.
        MethodNode constructor = new MethodNode(Opcodes.ACC_PUBLIC, "<init>", "()V", null, null);
        constructor.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        constructor.instructions.add(new MethodInsnNode(Opcodes.INVOKESTATIC, context, "get", "()L" + context + ";", false));
        constructor.instructions.add(new MethodInsnNode(Opcodes.INVOKESPECIAL, target.name, "<init>", signature, false));
        constructor.instructions.add(new InsnNode(Opcodes.RETURN));
        constructor.maxStack = 2;
        constructor.maxLocals = 1;
        target.methods.add(constructor);
    }
}
