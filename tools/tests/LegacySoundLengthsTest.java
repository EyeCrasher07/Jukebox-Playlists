import dev.eyecrasher.jukeboxplaylists.LegacySoundLengths;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Paths;

/** Tests production code against real encoded Vorbis files in separate jars. */
public final class LegacySoundLengthsTest {
    private static int checks;
    public static void main(String[] args) throws Exception {
        URL[] urls = new URL[args.length];
        for (int i = 0; i < args.length; i++) urls[i] = Paths.get(args[i]).toUri().toURL();
        try (URLClassLoader resources = new URLClassLoader(urls, null)) {
            LegacySoundLengths lengths = new LegacySoundLengths(resources);
            check(lengths, "playlist_length_fixture:disc.short", 45);
            check(lengths, "playlist_length_fixture:disc.long", 66);
            check(lengths, "playlist_length_fixture:disc.slow", 131);
            check(lengths, "playlist_length_fixture:disc.variants", 66);
            check(lengths, "test:nested_pitch", 131); // 0.5 * 0.5 is clamped to 0.5 by Minecraft
            check(lengths, "test:fast", 33);
            check(lengths, "test:default_namespace", 45);
            check(lengths, "test:merged", 66);
            check(lengths, "test:replaced", 45);
            check(lengths, "test:file_override", 66);
            for (String invalid : new String[]{"playlist_length_fixture:disc.missing", "test:unknown_variant",
                    "test:cycle_a", "test:cycle_b", "test:truncated", "test:no_eos", "test:not_vorbis",
                    "test:chained", "test:negative_pitch", "test:nan_pitch", "test:bad_id", "bad!", "missing:event"}) {
                check(lengths, invalid, -1);
            }
            check(lengths, "playlist_length_fixture:disc.long", 66); // repeat after failures and cache hits
        }
        System.out.println("LEGACY SOUND LENGTH TESTS PASSED: " + checks);
    }
    private static void check(LegacySoundLengths lengths, String id, long expected) {
        long actual = lengths.ticks(id);
        if (actual != expected) throw new AssertionError(id + ": expected " + expected + ", got " + actual);
        checks++;
    }
}
