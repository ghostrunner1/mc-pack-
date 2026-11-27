package ru.oleg.sporeguard;

import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Explosion;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.level.ExplosionEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.ServerTickEvent;

import java.util.IdentityHashMap;
import java.util.Map;

@Mod("sporeguard")
public class SporeGuard {
    private static final Map<EntityType<?>, Boolean> CACHE = new IdentityHashMap<>();
    private static int depth;

    public SporeGuard() {
        NeoForge.EVENT_BUS.addListener(SporeGuard::onTickPre);
        NeoForge.EVENT_BUS.addListener(SporeGuard::onTickPost);
        NeoForge.EVENT_BUS.addListener(SporeGuard::onServerTick);
        NeoForge.EVENT_BUS.addListener(SporeGuard::onDetonate);
    }

    public static boolean isSpore(Entity e) {
        if (e == null) return false;
        EntityType<?> t = e.getType();
        Boolean b = CACHE.get(t);
        if (b == null) {
            ResourceLocation k = EntityType.getKey(t);
            b = k != null && "spore".equals(k.getNamespace());
            CACHE.put(t, b);
        }
        return b;
    }

    public static boolean active() {
        return depth > 0;
    }

    private static void onTickPre(EntityTickEvent.Pre event) {
        Entity e = event.getEntity();
        if (!e.level().isClientSide() && isSpore(e)) depth++;
    }

    private static void onTickPost(EntityTickEvent.Post event) {
        Entity e = event.getEntity();
        if (!e.level().isClientSide() && isSpore(e) && depth > 0) depth--;
    }

    private static void onServerTick(ServerTickEvent.Post event) {
        depth = 0;
    }

    private static void onDetonate(ExplosionEvent.Detonate event) {
        Explosion ex = event.getExplosion();
        if (active() || isSpore(ex.getDirectSourceEntity())) event.getAffectedBlocks().clear();
    }
}
