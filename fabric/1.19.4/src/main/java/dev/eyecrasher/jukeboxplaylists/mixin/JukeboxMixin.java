package dev.eyecrasher.jukeboxplaylists.mixin;

import dev.eyecrasher.jukeboxplaylists.PlaylistJukebox;
import dev.eyecrasher.jukeboxplaylists.Playlists;
import dev.eyecrasher.jukeboxplaylists.Platform;
import dev.eyecrasher.jukeboxplaylists.LazoDiscsCompat;
import net.minecraft.core.BlockPos;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.JukeboxBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.JukeboxBlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;


@Mixin(JukeboxBlockEntity.class)
public abstract class JukeboxMixin implements PlaylistJukebox {
    @Unique private int playlist$cursor = -1;
    @Unique private int playlist$customEndDelay = -1;
    @Unique private ItemStack playlist$finishedItem = ItemStack.EMPTY;
    @Shadow private boolean isPlaying;

    @Override public int playlist$position() { return playlist$cursor; }
    @Override public void playlist$position(int position) { playlist$cursor = position; }
    @Override public ItemStack playlist$current() {
        return ((JukeboxBlockEntity) (Object) this).getItem(0);
    }

    @Override public void playlist$play(ItemStack stack) {
        JukeboxBlockEntity jukebox = (JukeboxBlockEntity) (Object) this;
        playlist$customEndDelay = -1;
        playlist$finishedItem = ItemStack.EMPTY;
        if (LazoDiscsCompat.play(this, stack)) return;
        jukebox.setItem(0, stack);
    }

    @Override public void playlist$tick() {
        JukeboxBlockEntity jukebox = (JukeboxBlockEntity) (Object) this;
        Level level = jukebox.getLevel();
        if (level == null || Platform.isClient(level) || jukebox.isRemoved()) return;
        if (LazoDiscsCompat.isCustom(playlist$current())) {
            // Keep vanilla's one-second gap, including for unavailable URLs;
            // never start a tight retry loop on the audio loader thread.
            if (playlist$current() != playlist$finishedItem) playlist$customEndDelay = -1;
            if (playlist$customEndDelay > 0 && --playlist$customEndDelay == 0) {
                playlist$customEndDelay = -1;
                Playlists.advance(this, true);
            }
        } else {
            boolean wasPlaying = isPlaying;
        JukeboxBlockEntity.playRecordTick(level, jukebox.getBlockPos(), jukebox.getBlockState(), jukebox);
        if (wasPlaying && !isPlaying) Playlists.advance(this, true);
        }
        if (playlist$current().isEmpty()) Playlists.advance(this, false);
    }

    @Override public void playlist$customFinished() {
        playlist$finishedItem = playlist$current();
        playlist$customEndDelay = 20;
    }



    @Inject(method = "load", at = @At("TAIL"))
    private void playlist$load(net.minecraft.nbt.CompoundTag tag, CallbackInfo ci) {
        playlist$cursor = tag.contains("playlist_position") ? tag.getInt("playlist_position") : -1;

    }

    @Inject(method = "saveAdditional", at = @At("TAIL"))
    private void playlist$save(net.minecraft.nbt.CompoundTag tag, CallbackInfo ci) {
        if (playlist$cursor >= 0) tag.putInt("playlist_position", playlist$cursor);

    }
}
