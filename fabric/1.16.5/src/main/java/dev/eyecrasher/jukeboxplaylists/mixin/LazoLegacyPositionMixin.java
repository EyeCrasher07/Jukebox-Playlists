package dev.eyecrasher.jukeboxplaylists.mixin;

import net.minecraft.core.BlockPos;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Replace a coordinate formatter absent from dedicated Minecraft 1.16.5. */
@Pseudo
@Mixin(targets = {
        "com.eyecrasher.lazodiscs.server.JukeboxPlaybackManager",
        "com.eyecrasher.lazodiscs.voice.PlasmoVoiceBridge"
}, remap = false)
public abstract class LazoLegacyPositionMixin {
    @Redirect(method = "*", at = @At(value = "INVOKE", remap = false,
            target = "Lnet/minecraft/class_2338;method_23854()Ljava/lang/String;"),
            remap = false, require = 0)
    private String playlist$coordinates(@Coerce Object position) {
        BlockPos pos = (BlockPos) position;
        return pos.getX() + ", " + pos.getY() + ", " + pos.getZ();
    }
}
