package dev.eyecrasher.jukeboxplaylists;

import net.minecraft.item.ItemStack;

/** Small bridge implemented by the vanilla jukebox block entity mixin. */
public interface PlaylistJukebox {
    ItemStack playlist$current();
    void playlist$play(ItemStack stack);
    int playlist$position();
    void playlist$position(int position);
    void playlist$tick();
    void playlist$customFinished();
}
