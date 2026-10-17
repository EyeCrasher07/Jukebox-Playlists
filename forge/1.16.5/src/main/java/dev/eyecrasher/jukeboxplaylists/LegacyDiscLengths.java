package dev.eyecrasher.jukeboxplaylists;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Properties;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.apache.logging.log4j.LogManager;
import net.minecraft.item.ItemStack;

/** Song metadata for releases before the server had native record durations. */
public final class LegacyDiscLengths {
    private static final Properties LENGTHS = load();
    private static final LegacySoundLengths SOUNDS = new LegacySoundLengths(LegacyDiscLengths.class.getClassLoader());
    private static final ConcurrentHashMap<String, CompletableFuture<Long>> DISCOVERED = new ConcurrentHashMap<>();
    private static final ExecutorService READER = Executors.newSingleThreadExecutor(task -> {
        Thread thread = new Thread(task, "Jukebox Playlists sound lengths");
        thread.setDaemon(true);
        return thread;
    });

    private LegacyDiscLengths() {}

    public static long ticks(ItemStack stack) {
        String value = LENGTHS.getProperty(stack.getItem().getDescriptionId());
        if (value != null) {
            try {
                long ticks = Long.parseLong(value);
                if (ticks > 0 && ticks <= Long.MAX_VALUE - 20) return ticks;
            } catch (NumberFormatException ignored) {}
        }
        if (!(stack.getItem() instanceof LegacyRecordSound)) return -1;
        String sound = ((LegacyRecordSound) stack.getItem()).playlist$soundId();
        if (sound == null) return -1;
        return DISCOVERED.computeIfAbsent(sound, id -> CompletableFuture.supplyAsync(() -> {
            long ticks = SOUNDS.ticks(id);
            if (ticks <= 0) LogManager.getLogger("Jukebox Playlists").warn(
                "Cannot determine length of {} ({}). If its audio is supplied only by a client resource pack, "
                + "set its ticks in config/jukebox-playlists-song-lengths.properties.",
                stack.getItem().getDescriptionId(), id);
            return ticks;
        }, READER)).getNow(-1L);
    }

    private static Properties load() {
        Properties lengths = new Properties();
        String[] discs = {"13", "cat", "blocks", "chirp", "far", "mall", "mellohi",
                          "stal", "strad", "ward", "11", "wait", "pigstep", "otherside", "5"};
        int[] seconds = {178, 185, 345, 185, 174, 197, 96, 150, 188, 251, 71, 238, 149, 195, 178};
        for (int i = 0; i < discs.length; i++) {
            lengths.setProperty("item.minecraft.music_disc_" + discs[i], Integer.toString(seconds[i] * 20));
        }
        Path file = Paths.get("config", "jukebox-playlists-song-lengths.properties");
        if (Files.isRegularFile(file)) {
            try (InputStream input = Files.newInputStream(file)) {
                lengths.load(input);
            } catch (IOException exception) {
                throw new IllegalStateException("Cannot read jukebox playlist song lengths: " + file, exception);
            }
        }
        return lengths;
    }
}
