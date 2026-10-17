#!/usr/bin/env python3
"""Generate small original tones for legacy disc regression fixtures only."""
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def prepare_resources(destination):
    cache = ROOT / 'build/fixtures/legacy-audio'
    cache.mkdir(parents=True, exist_ok=True)
    for name, seconds, rate, frequency in [('short', 2.25, 44100, 440), ('long', 3.25, 22050, 880)]:
        sound = cache / (name + '.ogg')
        if not sound.exists():
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                            f'sine=frequency={frequency}:sample_rate={rate}:duration={seconds}',
                            '-c:a', 'libvorbis', '-q:a', '2', str(sound)], check=True)
    folder = destination / 'assets/playlist_length_fixture'
    (folder / 'sounds').mkdir(parents=True, exist_ok=True)
    for name in ('short', 'long'):
        shutil.copyfile(cache / (name + '.ogg'), folder / 'sounds' / (name + '.ogg'))
    sounds = {
        'disc.short': {'sounds': [{'name': 'playlist_length_fixture:short', 'stream': True}]},
        'disc.long': {'sounds': ['playlist_length_fixture:long']},
        'disc.slow': {'sounds': [{'name': 'playlist_length_fixture:disc.long', 'type': 'event', 'pitch': 0.5}]},
        'disc.variants': {'sounds': ['playlist_length_fixture:short', 'playlist_length_fixture:long']},
        'disc.missing': {'sounds': ['playlist_length_fixture:absent']},
    }
    (folder / 'sounds.json').write_text(json.dumps(sounds, indent=2) + '\n')
    models = folder / 'models/item'
    models.mkdir(parents=True, exist_ok=True)
    names = {}
    for name, disc in [('short', 'far'), ('slow', 'mellohi'), ('variants', 'ward'), ('missing', '11')]:
        (models / (name + '.json')).write_text(json.dumps({'parent': 'minecraft:item/generated',
            'textures': {'layer0': 'minecraft:item/music_disc_' + disc}}) + '\n')
        names['item.playlist_length_fixture.' + name] = 'Test disc: ' + name
        names['item.playlist_length_fixture.' + name + '.desc'] = 'Original test tone'
    (folder / 'lang').mkdir(exist_ok=True)
    (folder / 'lang/en_us.json').write_text(json.dumps(names) + '\n')


def prepare_fixture(target, java_dir, resources):
    """Register genuine non-vanilla RecordItems in a test-only mod."""
    fabric = target['loader'] == 'fabric'
    if fabric:
        fields = '''
    private static Item shortDisc, slowDisc, variantsDisc, missingDisc;
    @Override public void onInitialize() {
        shortDisc = register("short"); slowDisc = register("slow");
        variantsDisc = register("variants"); missingDisc = register("missing");
    }
    private static Item register(String name) {
        net.minecraft.resources.ResourceLocation id = new net.minecraft.resources.ResourceLocation("playlist_length_fixture", "disc." + name);
        net.minecraft.sounds.SoundEvent sound = net.minecraft.core.Registry.register(net.minecraft.core.Registry.SOUND_EVENT, id, new net.minecraft.sounds.SoundEvent(id));
        return net.minecraft.core.Registry.register(net.minecraft.core.Registry.ITEM,
            new net.minecraft.resources.ResourceLocation("playlist_length_fixture", name), new TestDisc(() -> sound));
    }
'''
    else:
        fields = '''
    private static final net.minecraftforge.registries.DeferredRegister<net.minecraft.sounds.SoundEvent> SOUNDS =
        net.minecraftforge.registries.DeferredRegister.create(net.minecraftforge.registries.ForgeRegistries.SOUND_EVENTS, "playlist_length_fixture");
    private static final net.minecraftforge.registries.DeferredRegister<Item> ITEMS =
        net.minecraftforge.registries.DeferredRegister.create(net.minecraftforge.registries.ForgeRegistries.ITEMS, "playlist_length_fixture");
    private static final java.util.function.Supplier<Item> shortDisc = register("short"), slowDisc = register("slow"),
        variantsDisc = register("variants"), missingDisc = register("missing");
    public static void initialize() {
        net.minecraftforge.eventbus.api.IEventBus bus = net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext.get().getModEventBus();
        SOUNDS.register(bus); ITEMS.register(bus);
    }
    private static java.util.function.Supplier<Item> register(String name) {
        java.util.function.Supplier<net.minecraft.sounds.SoundEvent> sound = SOUNDS.register("disc." + name,
            () -> new net.minecraft.sounds.SoundEvent(new net.minecraft.resources.ResourceLocation("playlist_length_fixture", "disc." + name)));
        return ITEMS.register(name, () -> new TestDisc(sound));
    }
'''
    methods = '\n'.join('    public static Item ' + name + '() { return ' + name + ('' if fabric else '.get()') + '; }'
                        for name in ('shortDisc', 'slowDisc', 'variantsDisc', 'missingDisc'))
    source = '''package dev.eyecrasher.playlistchecks;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.RecordItem;
public final class LegacyDiscFixture''' + (' implements net.fabricmc.api.ModInitializer' if fabric else '') + ' {\n' + fields + methods + '''
    private static final class TestDisc extends RecordItem {
        TestDisc(java.util.function.Supplier<net.minecraft.sounds.SoundEvent> sound) {
            super(1, ''' + ('sound.get()' if fabric else 'sound') + ''', new Item.Properties().stacksTo(1));
        }
    }
}
'''
    dest = java_dir / 'dev/eyecrasher/playlistchecks/LegacyDiscFixture.java'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(source)
    prepare_resources(resources)
    if fabric:
        path = resources / 'fabric.mod.json'
        metadata = json.loads(path.read_text())
        metadata['entrypoints'] = {'main': ['dev.eyecrasher.playlistchecks.LegacyDiscFixture']}
        path.write_text(json.dumps(metadata, indent=2) + '\n')
    else:
        # The fixture is packaged separately from the production mod in clients.
        mod = next(java_dir.rglob('*Mod.java'))
        source = mod.read_text()
        initialize = 'dev.eyecrasher.playlistchecks.LegacyDiscFixture.initialize();'
        if 'public JukeboxPlaylistsMod() {}' in source:
            source = source.replace('public JukeboxPlaylistsMod() {}', 'public JukeboxPlaylistsMod() { ' + initialize + ' }')
        else:
            source = re.sub(r'public final class (\w+) \{\}',
                            lambda m: 'public final class ' + m[1] + ' { public ' + m[1] + '() { ' + initialize + ' } }', source)
        mod.write_text(source)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    prepare_resources(parser.parse_args().output)
