package ru.oleg.safezone;

import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;

@Mod("safezone")
public class SafeZone {
    private static final double MIN_X = -1488, MAX_X = -1088;
    private static final double MIN_Z = 2240, MAX_Z = 2848;

    public SafeZone() {
        NeoForge.EVENT_BUS.addListener(SafeZone::onJoin);
    }

    private static void onJoin(EntityJoinLevelEvent event) {
        if (event.getLevel().isClientSide()) return;
        if (!"minecraft:overworld".equals(event.getLevel().dimension().location().toString())) return;
        Entity e = event.getEntity();
        String id = String.valueOf(EntityType.getKey(e.getType()));
        if (!id.equals("skinwalker:skinwalker") && !id.equals("cave_dweller:cave_dweller")) return;
        double x = e.getX(), z = e.getZ();
        if (x >= MIN_X && x < MAX_X && z >= MIN_Z && z < MAX_Z) event.setCanceled(true);
    }
}
