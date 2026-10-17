package dev.eyecrasher.playlistpair;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import java.nio.file.*;
import java.util.List;
import java.util.concurrent.*;
import java.util.function.BooleanSupplier;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;

/** Client-only probe for two independent production clients. No server state access. */
public final class PairChecks {
    private static final Gson JSON = new Gson();
    private static final List<SoundInstance> RECORDS = new CopyOnWriteArrayList<>();
    private static final Minecraft MC = Minecraft.getInstance();
    private static final Path COORD = Path.of(System.getProperty("playlist.coord"));
    private static final String ROLE = System.getProperty("playlist.role");
    private static boolean started;

    public static void sound(SoundInstance sound) {
        if (sound.getSource() == SoundSource.RECORDS) {
            RECORDS.add(sound);
            System.out.println("PLAYLIST PAIR SOUND: " + sound.getIdentifier());
        }
    }

    public static void tick() {
        MC.options.pauseOnLostFocus = false;
        if (started || MC.player == null || MC.level == null) return;
        started = true;
        Thread worker = new Thread(() -> {
            try {
                if (MC.getSingleplayerServer() != null) throw new AssertionError("Expected a dedicated server connection");
                JsonObject ready = new JsonObject();
                ready.addProperty("pid", ProcessHandle.current().pid());
                ready.addProperty("java", System.getProperty("java.version"));
                ready.addProperty("role", ROLE);
                put(ROLE + "-ready.json", ready);
                int previous = -1;
                long deadline = System.nanoTime() + TimeUnit.MINUTES.toNanos(9);
                while (System.nanoTime() < deadline) {
                    Path request = COORD.resolve(ROLE + "-request.json");
                    if (!Files.exists(request)) { Thread.sleep(100); continue; }
                    JsonObject step = JSON.fromJson(Files.readString(request), JsonObject.class);
                    int id = step.get("id").getAsInt();
                    if (id == previous) { Thread.sleep(100); continue; }
                    previous = id;
                    String action = step.get("action").getAsString();
                    if (action.equals("quit")) {
                        put(id + "-" + ROLE + ".json", result(id));
                        System.out.println("PLAYLIST PAIR CLIENT PASSED: " + ROLE);
                        return;
                    }
                    if (action.equals("chest")) {
                        use(new BlockPos(0, 101, 0));
                        await(() -> call(() -> MC.gui.screen() instanceof net.minecraft.client.gui.screens.inventory.ContainerScreen), 10000);
                        screenshot();
                        client(() -> { MC.player.closeContainer(); return null; });
                    } else {
                        if (action.equals("skip")) use(new BlockPos(0, 100, 0));
                        String track = step.get("track").getAsString();
                        await(() -> call(() -> active(track) && activeCount() == 1), 110000);
                        screenshot();
                    }
                    put(id + "-" + ROLE + ".json", result(id));
                    System.out.println("PLAYLIST PAIR STEP PASSED: " + id + " " + ROLE);
                }
                throw new AssertionError("Pair supervisor deadline");
            } catch (Throwable failure) {
                failure.printStackTrace();
                JsonObject result = new JsonObject();
                result.addProperty("success", false);
                result.addProperty("error", failure.toString());
                try { put(ROLE + "-failure.json", result); } catch (Exception ignored) {}
                System.out.println("PLAYLIST PAIR CLIENT FAILED: " + ROLE);
            } finally {
                MC.execute(MC::stop);
            }
        }, "Playlist pair " + ROLE);
        worker.setDaemon(true);
        worker.start();
    }

    private static void use(BlockPos pos) throws Exception {
        client(() -> {
            MC.gameMode.useItemOn(MC.player, InteractionHand.MAIN_HAND,
                new BlockHitResult(Vec3.atCenterOf(pos), Direction.SOUTH, pos, false));
            return null;
        });
    }
    private static JsonObject result(int id) {
        JsonObject result = new JsonObject();
        result.addProperty("success", true);
        result.addProperty("id", id);
        result.addProperty("role", ROLE);
        result.addProperty("record_events", RECORDS.size());
        result.addProperty("active_records", call(() -> activeCount()));
        return result;
    }
    private static boolean active(String track) {
        for (SoundInstance sound : RECORDS)
            if (sound.getIdentifier().toString().endsWith("." + track) && MC.getSoundManager().isActive(sound)) return true;
        return false;
    }
    private static int activeCount() {
        int count = 0;
        for (SoundInstance sound : RECORDS) if (MC.getSoundManager().isActive(sound)) count++;
        return count;
    }
    private static void screenshot() throws Exception {
        Thread.sleep(1200);
        client(() -> { Screenshot.grab(MC, false); return null; });
        Thread.sleep(700);
    }
    private static void await(BooleanSupplier condition, long millis) throws Exception {
        long end = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(millis);
        while (!condition.getAsBoolean()) {
            if (System.nanoTime() > end) throw new AssertionError("Client step timed out");
            Thread.sleep(100);
        }
    }
    private static <T> T client(Callable<T> action) throws Exception {
        FutureTask<T> task = new FutureTask<>(action);
        MC.execute(task);
        return task.get(15, TimeUnit.SECONDS);
    }
    private static <T> T call(Callable<T> action) {
        try { return client(action); } catch (Exception failure) { throw new RuntimeException(failure); }
    }
    private static void put(String name, JsonObject result) throws Exception {
        Path temporary = COORD.resolve(name + ".tmp");
        Files.writeString(temporary, JSON.toJson(result));
        Files.move(temporary, COORD.resolve(name), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }
}
