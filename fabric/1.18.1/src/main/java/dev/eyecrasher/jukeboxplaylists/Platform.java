package dev.eyecrasher.jukeboxplaylists;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.item.ItemStack;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.item.RecordItem;
public final class Platform {
    private static final ResourceLocation CONTAINERS = new ResourceLocation("minecraft", "jukebox_containers");
    private Platform() {}
    public static boolean isClient(Level level) { return level.isClientSide; }
    public static boolean isPlaylistContainer(BlockState state) { return BlockTags.getAllTags().getTagOrEmpty(CONTAINERS).contains(state.getBlock()); }
    public static boolean isDisc(ItemStack stack) { return !stack.isEmpty() && stack.getItem() instanceof RecordItem; }
    public static boolean lazoSetterStartsPlayback() { return true; }
}
