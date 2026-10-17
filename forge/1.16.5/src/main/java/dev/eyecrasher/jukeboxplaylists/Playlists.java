package dev.eyecrasher.jukeboxplaylists;

import net.minecraft.util.math.BlockPos;
import net.minecraft.inventory.IInventory;
import net.minecraft.item.ItemStack;
import net.minecraft.world.World;
import net.minecraft.block.ChestBlock;
import net.minecraft.block.JukeboxBlock;
import net.minecraft.tileentity.TileEntity;
import net.minecraft.block.BlockState;
import net.minecraft.state.properties.ChestType;

public final class Playlists {
    private Playlists() {}

    public static void advance(PlaylistJukebox jukebox, boolean repeat) {
        TileEntity entity = (TileEntity) jukebox;
        World level = entity.getLevel();
        BlockPos position = entity.getBlockPos();
        // A removal can also stop a song. Never refill a destroyed jukebox.
        if (level == null || Platform.isClient(level) || entity.isRemoved()
                || level.getBlockEntity(position) != entity
                || !(level.getBlockState(position).getBlock() instanceof JukeboxBlock)) {
            return;
        }
        BlockState above = level.getBlockState(position.above());
        if (!Platform.isPlaylistContainer(above)
                || (above.getBlock() instanceof ChestBlock
                    && above.getValue(ChestBlock.TYPE) != ChestType.SINGLE)) {
            return;
        }
        TileEntity containerEntity = level.getBlockEntity(position.above());
        if (!(containerEntity instanceof IInventory)) {
            return;
        }
        IInventory chest = (IInventory) containerEntity;
        int size = chest.getContainerSize();
        ItemStack current = jukebox.playlist$current();
        // Vanilla discs cannot stack. Avoid truncating stacks made by other mods.
        if (current.getCount() > 1) {
            return;
        }
        int cursor = jukebox.playlist$position();
        if (cursor < -1 || cursor >= size) {
            cursor = -1;
        }
        for (int offset = 1; offset <= size; offset++) {
            int slot = (cursor + offset) % size;
            ItemStack candidate = chest.getItem(slot);
            if (candidate.getCount() == 1 && Platform.isDisc(candidate)) {
                // Keep the complete ItemStack, including names, NBT and components.
                chest.setItem(slot, current);
                jukebox.playlist$position(slot);
                jukebox.playlist$play(candidate);
                chest.setChanged();
                entity.setChanged();
                return;
            }
        }
        if (jukebox.playlist$position() != -1) {
            jukebox.playlist$position(-1);
            entity.setChanged();
        }
        if (repeat && Platform.isDisc(current)) {
            jukebox.playlist$play(current);
        }
    }
}
