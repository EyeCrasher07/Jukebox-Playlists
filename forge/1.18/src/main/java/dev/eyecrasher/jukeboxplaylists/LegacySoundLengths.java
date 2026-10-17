package dev.eyecrasher.jukeboxplaylists;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Reads bundled sound resources without loading any Minecraft client classes.
 * Used only by the single background reader in LegacyDiscLengths. */
public final class LegacySoundLengths {
    private final ClassLoader resources;
    private final Map<String, Map<String, List<JsonElement>>> namespaces = new HashMap<>();
    private final Map<String, Double> files = new HashMap<>();

    public LegacySoundLengths(ClassLoader resources) {
        this.resources = resources;
    }

    public long ticks(String soundId) {
        try {
            double seconds = event(soundId, 1.0, new HashSet<>());
            double ticks = Math.ceil(seconds * 20.0);
            return Double.isFinite(ticks) && ticks > 0 && ticks < Long.MAX_VALUE - 20 ? (long) ticks : -1;
        } catch (IOException | RuntimeException exception) {
            return -1;
        }
    }

    private double event(String id, double pitch, Set<String> visiting) throws IOException {
        id = identifier(id);
        if (visiting.size() >= 32 || !visiting.add(id)) return -1;
        try {
            int colon = id.indexOf(':');
            String namespace = id.substring(0, colon);
            Map<String, List<JsonElement>> definitions = namespaces.get(namespace);
            if (definitions == null) {
                definitions = definitions(namespace);
                namespaces.put(namespace, definitions);
            }
            List<JsonElement> sounds = definitions.get(id.substring(colon + 1));
            if (sounds == null || sounds.isEmpty()) return -1;
            double longest = -1;
            for (JsonElement sound : sounds) {
                String name;
                boolean reference = false;
                double entryPitch = 1;
                if (sound.isJsonPrimitive() && sound.getAsJsonPrimitive().isString()) {
                    name = sound.getAsString();
                } else {
                    JsonObject entry = sound.getAsJsonObject();
                    name = entry.get("name").getAsString();
                    if (entry.has("type")) {
                        String type = entry.get("type").getAsString();
                        if (!type.equals("file") && !type.equals("event")) return -1;
                        reference = type.equals("event");
                    }
                    if (entry.has("pitch")) entryPitch = entry.get("pitch").getAsDouble();
                }
                if (!Double.isFinite(entryPitch) || entryPitch <= 0) return -1;
                double seconds = reference ? event(name, pitch * entryPitch, visiting)
                    : file(identifier(name)) / Math.max(0.5, Math.min(2.0, pitch * entryPitch));
                // Random variants cannot be predicted by the server. Wait for
                // the longest one, and never guess if any variant is unknown.
                if (!(seconds > 0)) return -1;
                longest = Math.max(longest, seconds);
            }
            return longest;
        } finally {
            visiting.remove(id);
        }
    }

    private Map<String, List<JsonElement>> definitions(String namespace) throws IOException {
        Map<String, List<JsonElement>> result = new HashMap<>();
        Enumeration<URL> urls = resources.getResources("assets/" + namespace + "/sounds.json");
        while (urls.hasMoreElements()) {
            try (InputStream input = urls.nextElement().openStream();
                 InputStreamReader reader = new InputStreamReader(new LimitedInputStream(input, 4 * 1024 * 1024), StandardCharsets.UTF_8)) {
                JsonObject root = new JsonParser().parse(reader).getAsJsonObject();
                for (Map.Entry<String, JsonElement> entry : root.entrySet()) {
                    JsonObject event = entry.getValue().getAsJsonObject();
                    List<JsonElement> sounds = result.computeIfAbsent(entry.getKey(), key -> new ArrayList<>());
                    if (event.has("replace") && event.get("replace").getAsBoolean()) sounds.clear();
                    if (event.has("sounds")) for (JsonElement sound : event.getAsJsonArray("sounds")) sounds.add(sound);
                }
            }
        }
        return result;
    }

    private double file(String id) throws IOException {
        Double cached = files.get(id);
        if (cached != null) return cached;
        int colon = id.indexOf(':');
        Enumeration<URL> urls = resources.getResources("assets/" + id.substring(0, colon)
            + "/sounds/" + id.substring(colon + 1) + ".ogg");
        URL selected = null;
        while (urls.hasMoreElements()) selected = urls.nextElement();
        double seconds = -1;
        if (selected != null) {
            try (InputStream input = new BufferedInputStream(new LimitedInputStream(selected.openStream(), 256L * 1024 * 1024))) {
                seconds = vorbisSeconds(input);
            }
        }
        files.put(id, seconds);
        return seconds;
    }

    private static String identifier(String id) {
        if (id.indexOf(':') < 0) id = "minecraft:" + id;
        if (!id.matches("[a-z0-9_.-]+:[a-z0-9_./-]+") || id.contains("..")) {
            throw new IllegalArgumentException("Invalid sound identifier");
        }
        return id;
    }

    // Vorbis I appendix A: the EOS granule is the number of PCM samples.
    // Read Ogg page headers, not decoded audio; no native codec is needed.
    private static double vorbisSeconds(InputStream input) throws IOException {
        byte[] header = new byte[27];
        byte[] lacing = new byte[255];
        byte[] body = new byte[255 * 255];
        long serial = -1;
        long sequence = 0;
        long sampleRate = 0;
        long granule = -1;
        boolean continued = false;
        boolean ended = false;
        while (true) {
            int first = input.read();
            if (first < 0) break;
            if (ended) return -1; // Chained/multiplexed streams are not a Minecraft record.
            header[0] = (byte) first;
            read(input, header, 1, 26);
            if (header[0] != 'O' || header[1] != 'g' || header[2] != 'g' || header[3] != 'S'
                || header[4] != 0 || (header[5] & ~7) != 0) return -1;
            int segments = header[26] & 255;
            read(input, lacing, 0, segments);
            int size = 0;
            for (int i = 0; i < segments; i++) size += lacing[i] & 255;
            read(input, body, 0, size);
            long pageSerial = little(header, 14, 4);
            if (sampleRate == 0) {
                if (header[5] != 2 || size < 30 || body[0] != 1 || body[1] != 'v' || body[2] != 'o'
                    || body[3] != 'r' || body[4] != 'b' || body[5] != 'i' || body[6] != 's'
                    || little(body, 7, 4) != 0 || body[11] == 0 || (body[29] & 1) == 0) return -1;
                sampleRate = little(body, 12, 4);
                if (sampleRate == 0) return -1;
                serial = pageSerial;
            } else if ((header[5] & 2) != 0) return -1;
            if (serial != pageSerial || little(header, 18, 4) != sequence++
                || ((header[5] & 1) != 0) != continued) return -1;
            if (segments > 0) continued = (lacing[segments - 1] & 255) == 255;
            long pageGranule = little(header, 6, 8);
            if (pageGranule >= 0) {
                if (pageGranule < granule) return -1;
                granule = pageGranule;
            }
            ended = (header[5] & 4) != 0;
            if (ended && (continued || pageGranule <= 0)) return -1;
        }
        return ended && granule > 0 ? (double) granule / sampleRate : -1;
    }

    private static long little(byte[] bytes, int offset, int count) {
        long value = 0;
        for (int i = 0; i < count; i++) value |= (bytes[offset + i] & 255L) << (8 * i);
        return value;
    }

    private static void read(InputStream input, byte[] bytes, int offset, int length) throws IOException {
        while (length > 0) {
            int count = input.read(bytes, offset, length);
            if (count < 0) throw new IOException("Truncated Ogg page");
            if (count == 0) throw new IOException("Empty Ogg read");
            offset += count;
            length -= count;
        }
    }

    private static final class LimitedInputStream extends java.io.FilterInputStream {
        private long remaining;
        LimitedInputStream(InputStream input, long limit) { super(input); remaining = limit; }
        @Override public int read() throws IOException {
            int value = super.read();
            if (value >= 0 && --remaining < 0) throw new IOException("Sound resource is too large");
            return value;
        }
        @Override public int read(byte[] bytes, int offset, int length) throws IOException {
            int count = in.read(bytes, offset, (int) Math.min(length, remaining + 1));
            if (count > 0 && (remaining -= count) < 0) throw new IOException("Sound resource is too large");
            return count;
        }
    }
}
