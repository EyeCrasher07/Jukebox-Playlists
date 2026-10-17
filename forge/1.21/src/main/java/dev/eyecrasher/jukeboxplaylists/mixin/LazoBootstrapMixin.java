package dev.eyecrasher.jukeboxplaylists.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;

/** The config plugin supplies Forge 51's missing no-argument entry point. */
@Pseudo
@Mixin(targets = "com.eyecrasher.lazodiscs.LazoDiscs", remap = false)
public abstract class LazoBootstrapMixin {}
