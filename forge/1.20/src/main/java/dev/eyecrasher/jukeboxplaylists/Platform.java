package dev.eyecrasher.jukeboxplaylists;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.item.ItemStack;
import net.minecraft.tags.TagKey; import net.minecraft.world.level.block.Block;
import net.minecraft.world.item.RecordItem;
public final class Platform {
    private static final TagKey<Block> CONTAINERS = TagKey.create(net.minecraft.core.registries.Registries.BLOCK, new ResourceLocation("minecraft", "jukebox_containers"));
    private Platform() {}
    public static boolean isClient(Level level) { return level.isClientSide; }
    public static boolean isPlaylistContainer(BlockState state) { return state.is(CONTAINERS); }
    public static boolean isDisc(ItemStack stack) { return !stack.isEmpty() && stack.getItem() instanceof RecordItem; }
    public static boolean lazoSetterStartsPlayback() { return false; }
}
