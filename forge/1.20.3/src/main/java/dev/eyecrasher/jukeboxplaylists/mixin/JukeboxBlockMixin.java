package dev.eyecrasher.jukeboxplaylists.mixin;
import dev.eyecrasher.jukeboxplaylists.*;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.JukeboxBlock;
import net.minecraft.world.level.block.entity.*;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
@Mixin(JukeboxBlock.class)
public abstract class JukeboxBlockMixin {
    @Inject(method = "getTicker", at = @At("HEAD"), cancellable = true)
    private <T extends BlockEntity> void playlist$ticker(Level level, BlockState state,
            BlockEntityType<T> type, CallbackInfoReturnable<BlockEntityTicker<T>> ci) {
        if (!Platform.isClient(level) && type == BlockEntityType.JUKEBOX) {
            ci.setReturnValue((world, pos, blockState, entity) -> ((PlaylistJukebox) entity).playlist$tick());
        }
    }
}
