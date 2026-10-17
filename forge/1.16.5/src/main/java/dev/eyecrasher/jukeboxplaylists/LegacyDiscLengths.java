package dev.eyecrasher.jukeboxplaylists;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.apache.logging.log4j.LogManager;
import net.minecraft.item.ItemStack;

/** Song metadata for releases before the server had native record durations. */
public final class LegacyDiscLengths {
    private static final Map<String, Long> VANILLA = vanilla();
    private static final LegacySoundLengths SOUNDS = new LegacySoundLengths(LegacyDiscLengths.class.getClassLoader());
    private static final ConcurrentHashMap<String, CompletableFuture<Long>> DISCOVERED = new ConcurrentHashMap<>();
    private static final ExecutorService READER = Executors.newSingleThreadExecutor(task -> {
        Thread thread = new Thread(task, "Jukebox Playlists sound lengths");
        thread.setDaemon(true);
        return thread;
    });

    private LegacyDiscLengths() {}

    public static long ticks(ItemStack stack) {
        if (!(stack.getItem() instanceof LegacyRecordSound)) return -1;
        String sound = ((LegacyRecordSound) stack.getItem()).playlist$soundId();
        if (sound == null) return -1;
        Long vanilla = VANILLA.get(sound);
        if (vanilla != null) return vanilla;
        String item = stack.getItem().getDescriptionId();
        return DISCOVERED.computeIfAbsent(sound, id -> CompletableFuture.supplyAsync(() -> {
            long ticks = SOUNDS.ticks(id);
            if (ticks <= 0) LogManager.getLogger("Jukebox Playlists").warn(
                "Cannot determine length of {} ({}): no readable bundled OGG Vorbis audio.", item, id);
            return ticks;
        }, READER)).getNow(-1L);
    }

    private static Map<String, Long> vanilla() {
        Map<String, Long> lengths = new HashMap<>();
        String[] discs = {"13", "cat", "blocks", "chirp", "far", "mall", "mellohi",
                          "stal", "strad", "ward", "11", "wait", "pigstep", "otherside", "5"};
        int[] seconds = {178, 185, 345, 185, 174, 197, 96, 150, 188, 251, 71, 238, 149, 195, 178};
        for (int i = 0; i < discs.length; i++) {
            lengths.put("minecraft:music_disc." + discs[i], seconds[i] * 20L);
        }
        return lengths;
    }
}
