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
public abstract class JukeboxBlockMixin implements net.minecraft.world.level.block.EntityBlock {
    @Override public <T extends BlockEntity> BlockEntityTicker<T> getTicker(Level level, BlockState state, BlockEntityType<T> type) {
        if (!Platform.isClient(level) && type == BlockEntityType.JUKEBOX) {
            return (world, pos, blockState, entity) -> ((PlaylistJukebox) entity).playlist$tick();
        }
        return null;
    }
}
