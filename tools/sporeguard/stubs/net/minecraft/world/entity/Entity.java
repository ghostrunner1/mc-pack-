package net.minecraft.world.entity;
public abstract class Entity { public EntityType<?> getType() { return null; } public final double getX() { return 0; } public final double getZ() { return 0; } public final void discard() {} public net.minecraft.world.level.Level level() { return null; } }
