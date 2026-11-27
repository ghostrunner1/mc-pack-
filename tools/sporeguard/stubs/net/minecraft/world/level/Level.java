package net.minecraft.world.level;
public abstract class Level { public boolean isClientSide() { return false; } public final net.minecraft.resources.ResourceKey<Level> dimension() { return null; } public net.minecraft.world.level.block.state.BlockState getBlockState(net.minecraft.core.BlockPos p) { return null; } }
