package dev.eyecrasher.jukeboxplaylists;
import net.minecraft.util.ResourceLocation;
import net.minecraft.world.World;
import net.minecraft.block.BlockState;
import net.minecraft.item.ItemStack;
import net.minecraft.tags.BlockTags;
import net.minecraft.item.MusicDiscItem;
public final class Platform {
    private static final ResourceLocation CONTAINERS = new ResourceLocation("minecraft", "jukebox_containers");
    private Platform() {}
    public static boolean isClient(World level) { return level.isClientSide; }
    public static boolean isPlaylistContainer(BlockState state) { return BlockTags.getAllTags().getTagOrEmpty(CONTAINERS).contains(state.getBlock()); }
    public static boolean isDisc(ItemStack stack) { return !stack.isEmpty() && stack.getItem() instanceof MusicDiscItem; }
    public static boolean lazoSetterStartsPlayback() { return true; }
}
