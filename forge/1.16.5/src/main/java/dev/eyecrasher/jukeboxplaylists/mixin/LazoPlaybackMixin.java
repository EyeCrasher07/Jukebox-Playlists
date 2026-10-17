package dev.eyecrasher.jukeboxplaylists.mixin;

import dev.eyecrasher.jukeboxplaylists.LazoDiscsCompat;
import java.util.Map;
import net.minecraft.util.math.BlockPos;
import net.minecraft.world.World;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Run only after LazoDiscs accepts completion of its current audio source. */
@Pseudo
@Mixin(targets = "com.eyecrasher.lazodiscs.server.JukeboxPlaybackManager", remap = false)
public abstract class LazoPlaybackMixin {
    @Redirect(method = "finishAt", at = @At(value = "INVOKE",
            target = "Ljava/util/Map;remove(Ljava/lang/Object;Ljava/lang/Object;)Z"), remap = false)
    private boolean playlist$finished(Map<?, ?> active, Object key, Object value,
            @Coerce Object world, @Coerce Object position, @Coerce Object source, String reason) {
        boolean removed = active.remove(key, value);
        if (removed) LazoDiscsCompat.finished((World) world, (BlockPos) position);
        return removed;
    }
}
