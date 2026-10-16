#!/usr/bin/env python3
"""Generate the small API-dependent bridge; playlist behavior stays shared."""
import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "dev/eyecrasher/jukeboxplaylists"


def version(value):
    return tuple(map(int, value.split(".")))


def prepare(target, output, tests=False):
    mc = target["minecraft"]
    v = version(mc)
    legacy = v < (1, 19, 1)
    classic = (1, 19, 1) <= v < (1, 19, 4)
    songs = v >= (1, 21)
    values = v >= (1, 21, 6)
    old_save = v < (1, 18)
    java_dir = output / "java"
    resources = output / "resources"
    java_dir.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / "src/main/java").rglob("*.java"):
        dest = java_dir / source.relative_to(ROOT / "src/main/java")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    if legacy:
        dest = java_dir / PACKAGE / "LegacyDiscLengths.java"
        shutil.copyfile(ROOT / "src/legacy/java" / PACKAGE / "LegacyDiscLengths.java", dest)
    fields = "@Unique private long playlist$elapsed;" if legacy else "@Shadow private boolean isPlaying;" if not songs else ""
    get_item = "getRecord()" if legacy or classic else "getItem(0)" if v < (1, 20, 3) else "getTheItem()"
    if legacy or classic:
        set_item = '''jukebox.setRecord(stack);
        Level level = jukebox.getLevel();
        level.setBlock(jukebox.getBlockPos(), jukebox.getBlockState().setValue(JukeboxBlock.HAS_RECORD, !stack.isEmpty()), 2);
        if (!stack.isEmpty()) {
            @START@
            level.levelEvent(1010, jukebox.getBlockPos(), Item.getId(stack.getItem()));
        }
        level.updateNeighborsAt(jukebox.getBlockPos(), jukebox.getBlockState().getBlock());
        jukebox.setChanged();'''.replace("@START@", "jukebox.playRecord();" if classic else "playlist$elapsed = 0;")
    else:
        set_item = "jukebox.setItem(0, stack);" if v < (1, 20, 3) else "jukebox.setTheItem(stack);"
    if legacy:
        tick = '''if (!playlist$current().isEmpty() && playlist$elapsed >= 0) {
            long length = dev.eyecrasher.jukeboxplaylists.LegacyDiscLengths.ticks(playlist$current());
            if (length > 0 && playlist$elapsed++ >= length + 20) {
                playlist$elapsed = -1;
                Playlists.advance(this, true);
            }
            if (playlist$elapsed > 0 && playlist$elapsed % 200 == 0) jukebox.setChanged();
        }'''
    else:
        playing = "jukebox.getSongPlayer().isPlaying()" if songs else "isPlaying"
        native_tick = "tick" if songs else "playRecordTick"
        tick = f'''boolean wasPlaying = {playing};
        JukeboxBlockEntity.{native_tick}(level, jukebox.getBlockPos(), jukebox.getBlockState(), jukebox);
        if (wasPlaying && !{playing}) Playlists.advance(this, true);'''
    extra = '''@Inject(method = "setRecord", at = @At("TAIL"))
    private void playlist$recordChanged(ItemStack stack, CallbackInfo ci) { playlist$elapsed = 0; }''' if legacy else ""
    if mc == "1.16.5":
        extra += "\n    @Override public void tick() { playlist$tick(); }"
    load_args = "net.minecraft.nbt.CompoundTag tag"
    if mc == "1.16.5":
        load_args = "BlockState state, " + load_args
    save_args = "net.minecraft.nbt.CompoundTag tag"
    if v >= (1, 20, 5):
        load_args += ", net.minecraft.core.HolderLookup.Provider registries"
        save_args += ", net.minecraft.core.HolderLookup.Provider registries"
    if values:
        load_args = "net.minecraft.world.level.storage.ValueInput tag"
        save_args = "net.minecraft.world.level.storage.ValueOutput tag"
    read_cursor = 'tag.getIntOr("playlist_position", -1)' if v >= (1, 21, 5) else 'tag.contains("playlist_position") ? tag.getInt("playlist_position") : -1'
    replacements = {
        "IMPORTS": "", "INTERFACES": ", net.minecraft.world.level.block.entity.TickableBlockEntity" if mc == "1.16.5" else "",
        "FIELDS": fields, "GET_ITEM": get_item, "SET_ITEM": set_item, "TICK": tick,
        "EXTRA_METHODS": extra, "LOAD_METHOD": "loadAdditional" if v >= (1, 20, 5) else "load",
        "LOAD_ARGS": load_args, "SAVE_METHOD": "save" if old_save else "saveAdditional",
        "SAVE_ARGS": save_args, "SAVE_CALLBACK": "CallbackInfoReturnable<net.minecraft.nbt.CompoundTag>" if old_save else "CallbackInfo",
        "READ_CURSOR": read_cursor,
        "READ_TIMER": 'playlist$elapsed = tag.contains("jukebox_playlists:elapsed") ? tag.getLong("jukebox_playlists:elapsed") : 0;' if legacy else "",
        "SAVE_TIMER": 'tag.putLong("jukebox_playlists:elapsed", playlist$elapsed);' if legacy else "",
    }
    source = (ROOT / "src/templates/JukeboxMixin.java.in").read_text()
    for key, value in replacements.items():
        source = source.replace("@" + key + "@", value)
    write(java_dir / PACKAGE / "mixin/JukeboxMixin.java", source)
    if mc != "1.16.5":
        method = '''@Inject(method = "getTicker", at = @At("HEAD"), cancellable = true)
    private <T extends BlockEntity> void playlist$ticker(Level level, BlockState state,
            BlockEntityType<T> type, CallbackInfoReturnable<BlockEntityTicker<T>> ci) {
        if (!Platform.isClient(level) && type == BlockEntityType.JUKEBOX) {
            ci.setReturnValue((world, pos, blockState, entity) -> ((PlaylistJukebox) entity).playlist$tick());
        }
    }''' if not legacy else '''@Override public <T extends BlockEntity> BlockEntityTicker<T> getTicker(Level level, BlockState state, BlockEntityType<T> type) {
        if (!Platform.isClient(level) && type == BlockEntityType.JUKEBOX) {
            return (world, pos, blockState, entity) -> ((PlaylistJukebox) entity).playlist$tick();
        }
        return null;
    }'''
        block_type = "BlockEntityTypes" if v >= (26, 2) else "BlockEntityType"
        method = method.replace("type == BlockEntityType.JUKEBOX", f"type == {block_type}.JUKEBOX")
        write(java_dir / PACKAGE / "mixin/JukeboxBlockMixin.java", '''package dev.eyecrasher.jukeboxplaylists.mixin;
import dev.eyecrasher.jukeboxplaylists.*;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.JukeboxBlock;
import net.minecraft.world.level.block.entity.*;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
@Mixin(JukeboxBlock.class)
public abstract class JukeboxBlockMixin''' + (" implements net.minecraft.world.level.block.EntityBlock" if legacy else "") + ''' {
    ''' + method + "\n}\n")
    identifier = "Identifier" if v >= (1, 21, 11) else "ResourceLocation"
    ident = f'{identifier}.fromNamespaceAndPath("minecraft", "jukebox_containers")' if v >= (1, 21) else f'new {identifier}("minecraft", "jukebox_containers")'
    if v < (1, 18, 2):
        tag_import = "import net.minecraft.tags.BlockTags;"
        tag_field = f"private static final {identifier} CONTAINERS = {ident};"
        check_tag = "BlockTags.getAllTags().getTagOrEmpty(CONTAINERS).contains(state.getBlock())"
    else:
        registry = "net.minecraft.core.Registry.BLOCK_REGISTRY" if v < (1, 19, 3) else "net.minecraft.core.registries.Registries.BLOCK"
        tag_import = "import net.minecraft.tags.TagKey; import net.minecraft.world.level.block.Block;"
        tag_field = f"private static final TagKey<Block> CONTAINERS = TagKey.create({registry}, {ident});"
        check_tag = "state.is(CONTAINERS)"
    client = "level.isClientSide()" if v >= (1, 21, 9) else "level.isClientSide"
    disc_import = "import net.minecraft.core.component.DataComponents;" if songs else "import net.minecraft.world.item.RecordItem;"
    disc = "stack.has(DataComponents.JUKEBOX_PLAYABLE)" if songs else "stack.getItem() instanceof RecordItem"
    write(java_dir / PACKAGE / "Platform.java", f'''package dev.eyecrasher.jukeboxplaylists;
import net.minecraft.resources.{identifier};
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.item.ItemStack;
{tag_import}
{disc_import}
public final class Platform {{
    {tag_field}
    private Platform() {{}}
    public static boolean isClient(Level level) {{ return {client}; }}
    public static boolean isPlaylistContainer(BlockState state) {{ return {check_tag}; }}
    public static boolean isDisc(ItemStack stack) {{ return !stack.isEmpty() && {disc}; }}
}}
''')
    if target["loader"] != "fabric":
        namespace = "net.neoforged.fml.common" if target["loader"] == "neoforge" and v >= (1, 20, 2) else "net.minecraftforge.fml.common"
        write(java_dir / PACKAGE / "JukeboxPlaylistsMod.java", f'''package dev.eyecrasher.jukeboxplaylists;
import {namespace}.Mod;
@Mod("jukebox_playlists")
public final class JukeboxPlaylistsMod {{ public JukeboxPlaylistsMod() {{}} }}
''')
    compatibility = "JAVA_8" if mc == "1.16.5" else "JAVA_16" if v < (1, 18) else "JAVA_17" if v < (1, 20, 5) else "JAVA_21"
    config = {"required": True, "minVersion": "0.8", "package": "dev.eyecrasher.jukeboxplaylists.mixin",
              "compatibilityLevel": compatibility, "mixins": ["JukeboxMixin"] + ([] if mc == "1.16.5" else ["JukeboxBlockMixin"]),
              "injectors": {"defaultRequire": 1}}
    if (target["loader"] == "forge" and v < (1, 20, 5)) or (target["loader"] == "neoforge" and mc == "1.20.1"):
        config["refmap"] = "main.refmap.json"
    write(resources / "jukebox-playlists.mixins.json", json.dumps(config, indent=2) + "\n")
    tag = {"replace": False, "values": ["minecraft:chest", "minecraft:trapped_chest"] +
           [{"id": "minecraft:" + wax + oxidation + "copper_chest", "required": False}
            for wax in ("", "waxed_") for oxidation in ("", "exposed_", "weathered_", "oxidized_")]}
    write(resources / ("data/minecraft/tags/" + ("block" if v >= (1, 21) else "blocks") + "/jukebox_containers.json"), json.dumps(tag, indent=2) + "\n")
    formats = json.loads((ROOT / "pack-versions.json").read_text())[mc]
    data_format = formats if isinstance(formats, int) else formats.get("data", formats.get("data_major"))
    resource_format = formats if isinstance(formats, int) else formats.get("resource", formats.get("resource_major"))
    pack = {"description": "Jukebox Playlists", "pack_format": data_format}
    if v >= (1, 21, 9):
        pack.update(min_format=[resource_format, 0], max_format=[data_format, formats.get("data_minor", 0)])
    elif v >= (1, 20, 2):
        pack["supported_formats"] = [resource_format, data_format]
    write(resources / "pack.mcmeta", json.dumps({"pack": pack}, indent=2) + "\n")
    mod_version = json.loads((ROOT / "versions.json").read_text())["mod_version"]
    if target["loader"] == "fabric":
        metadata = {"schemaVersion": 1, "id": "jukebox_playlists", "version": mod_version,
                    "name": "Jukebox Playlists", "description": "Chest playlists for vanilla jukeboxes, backported from 26.4.",
                    "environment": "*", "mixins": ["jukebox-playlists.mixins.json"],
                    "depends": {"fabricloader": ">=0.19.5", "minecraft": "=" + mc, "java": ">=" + str(target["java"])}}
        old_api_id = mc in {"1.16.5", "1.17", "1.17.1", "1.18", "1.18.1", "1.19", "1.19.1"}
        metadata["depends"]["fabric" if old_api_id else "fabric-api"] = "*"
        write(resources / "fabric.mod.json", json.dumps(metadata, indent=2) + "\n")
    else:
        neo = target["loader"] == "neoforge" and v >= (1, 20, 2)
        language_version = "[1,)" if neo else "[36,)"
        filename = "neoforge.mods.toml" if neo and v >= (1, 20, 5) else "mods.toml"
        metadata = f'''modLoader="javafml"
loaderVersion="{language_version}"
license="Unspecified"
[[mods]]
modId="jukebox_playlists"
version="{mod_version}"
displayName="Jukebox Playlists"
description="Chest playlists for vanilla jukeboxes, backported from 26.4."
[[dependencies.jukebox_playlists]]
modId="minecraft"
mandatory=true
versionRange="[{mc}]"
ordering="NONE"
side="BOTH"
'''
        if neo:
            if v >= (1, 20, 4):
                metadata = metadata.replace('mandatory=true', 'type="required"')
            metadata += '\n[[mixins]]\nconfig="jukebox-playlists.mixins.json"\n'
        write(resources / "META-INF" / filename, metadata)
    if tests:
        prepare_tests(target, java_dir, resources)
    if target["loader"] == "forge" and mc == "1.16.5":
        adapt_forge1165(java_dir)


def prepare_tests(target, java_dir, resources):
    mc = target["minecraft"]
    v = version(mc)
    name = 'named.setHoverName(new net.minecraft.network.chat.TextComponent("Keep this name"));' if v < (1, 19) else 'named.setHoverName(net.minecraft.network.chat.Component.literal("Keep this name"));' if v < (1, 20, 5) else 'named.set(net.minecraft.core.component.DataComponents.CUSTOM_NAME, net.minecraft.network.chat.Component.literal("Keep this name"));'
    save = "entity.save(new CompoundTag())" if v < (1, 18) else "entity.saveWithFullMetadata()" if v < (1, 20, 5) else "entity.saveWithFullMetadata(world.registryAccess())"
    load = "BlockEntity.loadStatic(entity.getBlockState(), saved)" if mc == "1.16.5" else "BlockEntity.loadStatic(POS, entity.getBlockState(), saved)" if v < (1, 20, 5) else "BlockEntity.loadStatic(POS, entity.getBlockState(), saved, world.registryAccess())"
    eject = "entity.popOutTheItem();" if v >= (1, 21) else "entity.popOutRecord();" if v >= (1, 19, 4) else "((JukeboxBlock) Blocks.JUKEBOX).use(world.getBlockState(POS), world, POS, null, InteractionHand.MAIN_HAND, new BlockHitResult(Vec3.atCenterOf(POS), Direction.UP, POS, false));"
    tick = "((net.minecraft.world.level.block.entity.TickableBlockEntity) entity).tick();" if mc == "1.16.5" else "((JukeboxBlock) Blocks.JUKEBOX).getTicker(world, entity.getBlockState(), (net.minecraft.world.level.block.entity.BlockEntityType) entity.getType()).tick(world, POS, entity.getBlockState(), entity);"
    source = (ROOT / "src/templates/PlaylistSmoke.java.in").read_text()
    copper = ""
    if v >= (1, 21, 9):
        variants = [wax + oxidation + "copper_chest" for wax in ("", "waxed_") for oxidation in ("", "exposed_", "weathered_", "oxidized_")]
        identifier = "Identifier" if v >= (1, 21, 11) else "ResourceLocation"
        copper = "for (String chestId : new String[]{" + ", ".join(json.dumps(b) for b in variants) + "}) {\n" + f'''
            net.minecraft.world.level.block.Block copper = net.minecraft.core.registries.BuiltInRegistries.BLOCK.getValue(net.minecraft.resources.{identifier}.fromNamespaceAndPath("minecraft", chestId));
''' + '''
            reset();
            world.setBlock(POS.above(), copper.defaultBlockState(), 3);
            chest = (Container) world.getBlockEntity(POS.above());
            chest.setItem(0, new ItemStack(Items.MUSIC_DISC_CAT));
            tick();
            check(box.playlist$current().getItem() == Items.MUSIC_DISC_CAT, "copper chest variant supports playlists: " + copper);
        }'''
    for key, value in {"NAME_STACK": name, "SAVE_ENTITY": save, "LOAD_ENTITY": load, "EJECT": eject, "TICK_INSTALLED": tick, "COPPER_TESTS": copper}.items():
        source = source.replace("@" + key + "@", value)
    write(java_dir / PACKAGE / "PlaylistSmoke.java", source)
    write(java_dir / PACKAGE / "mixin/ServerTestMixin.java", '''package dev.eyecrasher.jukeboxplaylists.mixin;
import net.minecraft.server.MinecraftServer;
import org.spongepowered.asm.mixin.*;
import org.spongepowered.asm.mixin.injection.*;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
@Mixin(MinecraftServer.class)
public abstract class ServerTestMixin {
    @Unique private boolean playlist$tested;
    @Inject(method = "tickServer", at = @At("TAIL"))
    private void playlist$test(CallbackInfo ci) {
        if (!playlist$tested) {
            playlist$tested = true;
            dev.eyecrasher.jukeboxplaylists.PlaylistSmoke.run((MinecraftServer) (Object) this);
        }
    }
}
''')
    path = resources / "jukebox-playlists.mixins.json"
    config = json.loads(path.read_text())
    config["mixins"].append("ServerTestMixin")
    write(path, json.dumps(config, indent=2) + "\n")
    if target["loader"] == "forge" and mc == "1.16.5":
        # Mavenizer's legacy combined jar omits the userdev service descriptors.
        write(resources / "META-INF/services/cpw.mods.modlauncher.api.ILaunchHandlerService",
              "net.minecraftforge.userdev.FMLUserdevServerLaunchProvider\n")
        write(resources / "META-INF/services/cpw.mods.modlauncher.api.INameMappingService",
              "net.minecraftforge.userdev.MCPNamingService\n")
        write(resources / "META-INF/services/net.minecraftforge.forgespi.locating.IModLocator",
              "net.minecraftforge.userdev.ClasspathLocator\n")


def adapt_forge1165(java_dir):
    # Forge 36 keeps MCP class/package names, with official Mojang member names.
    classes = {
        "net.minecraft.core.BlockPos": "net.minecraft.util.math.BlockPos",
        "net.minecraft.world.Container": "net.minecraft.inventory.IInventory",
        "net.minecraft.world.item.ItemStack": "net.minecraft.item.ItemStack",
        "net.minecraft.world.item.Item": "net.minecraft.item.Item",
        "net.minecraft.world.item.RecordItem": "net.minecraft.item.MusicDiscItem",
        "net.minecraft.world.item.Items": "net.minecraft.item.Items",
        "net.minecraft.world.level.Level": "net.minecraft.world.World",
        "net.minecraft.world.level.block.ChestBlock": "net.minecraft.block.ChestBlock",
        "net.minecraft.world.level.block.JukeboxBlock": "net.minecraft.block.JukeboxBlock",
        "net.minecraft.world.level.block.Blocks": "net.minecraft.block.Blocks",
        "net.minecraft.world.level.block.entity.JukeboxBlockEntity": "net.minecraft.tileentity.JukeboxTileEntity",
        "net.minecraft.world.level.block.entity.BlockEntity": "net.minecraft.tileentity.TileEntity",
        "net.minecraft.world.level.block.entity.TickableBlockEntity": "net.minecraft.tileentity.ITickableTileEntity",
        "net.minecraft.world.level.block.state.BlockState": "net.minecraft.block.BlockState",
        "net.minecraft.world.level.block.state.properties.ChestType": "net.minecraft.state.properties.ChestType",
        "net.minecraft.resources.ResourceLocation": "net.minecraft.util.ResourceLocation",
        "net.minecraft.nbt.CompoundTag": "net.minecraft.nbt.CompoundNBT",
        "net.minecraft.world.InteractionHand": "net.minecraft.util.Hand",
        "net.minecraft.core.Direction": "net.minecraft.util.Direction",
        "net.minecraft.world.phys.BlockHitResult": "net.minecraft.util.math.BlockRayTraceResult",
        "net.minecraft.world.phys.Vec3": "net.minecraft.util.math.vector.Vector3d",
        "net.minecraft.network.chat.TextComponent": "net.minecraft.util.text.StringTextComponent",
    }
    for file in java_dir.rglob("*.java"):
        text = file.read_text()
        for original, mapped in classes.items():
            text = re.sub(r"\b" + re.escape(original) + r"\b", mapped, text)
        for original, mapped in classes.items():
            if original.rsplit(".", 1)[1] != mapped.rsplit(".", 1)[1]:
                text = re.sub(r"\b" + original.rsplit(".", 1)[1] + r"\b", mapped.rsplit(".", 1)[1], text)
        file.write_text(text)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tests", action="store_true")
    args = parser.parse_args()
    target = next(t for t in json.loads((ROOT / "versions.json").read_text())["targets"] if t["id"] == args.target)
    prepare(target, args.output, args.tests)


if __name__ == "__main__":
    main()
