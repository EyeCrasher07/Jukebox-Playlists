package dev.eyecrasher.jukeboxplaylists;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Properties;
import net.minecraft.item.ItemStack;

/** Song metadata for releases before the server had native record durations. */
public final class LegacyDiscLengths {
    private static final Properties LENGTHS = load();

    private LegacyDiscLengths() {}

    public static long ticks(ItemStack stack) {
        String value = LENGTHS.getProperty(stack.getItem().getDescriptionId());
        if (value == null) {
            return -1;
        }
        try {
            long ticks = Long.parseLong(value);
            return ticks > 0 ? ticks : -1;
        } catch (NumberFormatException ignored) {
            return -1;
        }
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
