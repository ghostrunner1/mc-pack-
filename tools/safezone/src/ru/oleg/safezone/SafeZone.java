package ru.oleg.safezone;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.RegisterCommandsEvent;
import net.neoforged.neoforge.event.entity.EntityJoinLevelEvent;
import net.neoforged.neoforge.event.server.ServerStartingEvent;
import net.neoforged.neoforge.event.tick.ServerTickEvent;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Mod("safezone")
public class SafeZone {
    record Zone(String name, String dim, int minX, int minZ, int maxX, int maxZ) {
        boolean contains(String d, double x, double z) {
            return dim.equals(d) && x >= minX && x < maxX + 1 && z >= minZ && z < maxZ + 1;
        }
        String describe() {
            return name + " [" + dim + "] X " + minX + ".." + maxX + ", Z " + minZ + ".." + maxZ;
        }
    }

    private static final List<Zone> ZONES = new ArrayList<>();
    private static final Map<String, int[]> POS1 = new HashMap<>();
    private static final Map<String, int[]> POS2 = new HashMap<>();
    private static Path file;
    private static int tick;

    public SafeZone() {
        NeoForge.EVENT_BUS.addListener(SafeZone::onJoin);
        NeoForge.EVENT_BUS.addListener(SafeZone::onStarting);
        NeoForge.EVENT_BUS.addListener(SafeZone::onCommands);
        NeoForge.EVENT_BUS.addListener(SafeZone::onTick);
    }

    private static boolean isHorror(Entity e) {
        String id = String.valueOf(EntityType.getKey(e.getType()));
        return id.equals("skinwalker:skinwalker") || id.equals("cave_dweller:cave_dweller");
    }

    private static boolean inZone(String dim, double x, double z) {
        synchronized (ZONES) {
            for (Zone zn : ZONES) if (zn.contains(dim, x, z)) return true;
        }
        return false;
    }

    private static void onJoin(EntityJoinLevelEvent event) {
        if (event.getLevel().isClientSide()) return;
        Entity e = event.getEntity();
        if (!isHorror(e)) return;
        String dim = event.getLevel().dimension().location().toString();
        if (inZone(dim, e.getX(), e.getZ())) event.setCanceled(true);
    }

    private static void onTick(ServerTickEvent.Post event) {
        if (++tick < 20) return;
        tick = 0;
        if (ZONES.isEmpty()) return;
        for (ServerLevel level : event.getServer().getAllLevels()) {
            String dim = level.dimension().location().toString();
            List<Entity> kill = new ArrayList<>();
            for (Entity e : level.getAllEntities()) {
                if (e != null && isHorror(e) && inZone(dim, e.getX(), e.getZ())) kill.add(e);
            }
            for (Entity e : kill) e.discard();
        }
    }

    private static void onStarting(ServerStartingEvent event) {
        MinecraftServer server = event.getServer();
        file = server.getWorldPath(new LevelResource("data")).resolve("safezone.txt");
        load();
    }

    private static void load() {
        synchronized (ZONES) {
            ZONES.clear();
            try {
                if (!Files.exists(file)) {
                    ZONES.add(new Zone("base", "minecraft:overworld", -1488, 2240, -1089, 2847));
                    save();
                    return;
                }
                for (String line : Files.readAllLines(file, StandardCharsets.UTF_8)) {
                    line = line.trim();
                    if (line.isEmpty() || line.startsWith("#")) continue;
                    String[] p = line.split("\\s+");
                    if (p.length != 6) continue;
                    ZONES.add(new Zone(p[0], p[1], Integer.parseInt(p[2]), Integer.parseInt(p[3]),
                            Integer.parseInt(p[4]), Integer.parseInt(p[5])));
                }
            } catch (Exception ex) {
                System.err.println("[safezone] failed to load " + file + ": " + ex);
            }
        }
    }

    private static void save() {
        synchronized (ZONES) {
            List<String> out = new ArrayList<>();
            out.add("# name dimension minX minZ maxX maxZ (block coords, inclusive). Edit via /safezone.");
            for (Zone z : ZONES)
                out.add(z.name + " " + z.dim + " " + z.minX + " " + z.minZ + " " + z.maxX + " " + z.maxZ);
            try {
                Files.createDirectories(file.getParent());
                Files.write(file, out, StandardCharsets.UTF_8);
            } catch (Exception ex) {
                System.err.println("[safezone] failed to save " + file + ": " + ex);
            }
        }
    }

    private static void ok(CommandSourceStack s, String msg, boolean broadcast) {
        s.sendSuccess(() -> Component.literal(msg), broadcast);
    }

    private static int fail(CommandSourceStack s, String msg) {
        s.sendFailure(Component.literal(msg));
        return 0;
    }

    private static int addZone(CommandSourceStack s, String name, String dim, int x1, int z1, int x2, int z2) {
        Zone z = new Zone(name, dim, Math.min(x1, x2), Math.min(z1, z2), Math.max(x1, x2), Math.max(z1, z2));
        synchronized (ZONES) {
            for (Zone o : ZONES) if (o.name.equals(name)) return fail(s, "Зона «" + name + "» уже есть. Сначала /safezone remove " + name);
            ZONES.add(z);
            save();
        }
        ok(s, "Безопасная зона добавлена: " + z.describe(), true);
        return 1;
    }

    private static int[] here(CommandSourceStack s) {
        Vec3 p = s.getPosition();
        return new int[]{(int) Math.floor(p.x()), (int) Math.floor(p.z())};
    }

    private static String dimOf(CommandSourceStack s) {
        return s.getLevel().dimension().location().toString();
    }

    private static int setPos(CommandContext<CommandSourceStack> c, boolean first) {
        CommandSourceStack s = c.getSource();
        int[] p = here(s);
        (first ? POS1 : POS2).put(s.getTextName(), new int[]{p[0], p[1]});
        ok(s, (first ? "Угол 1" : "Угол 2") + ": X " + p[0] + ", Z " + p[1], false);
        return 1;
    }

    private static void onCommands(RegisterCommandsEvent event) {
        CommandDispatcher<CommandSourceStack> d = event.getDispatcher();
        d.register(Commands.literal("safezone")
                .requires(s -> s.hasPermission(2))
                .then(Commands.literal("list").executes(c -> {
                    CommandSourceStack s = c.getSource();
                    synchronized (ZONES) {
                        if (ZONES.isEmpty()) return fail(s, "Безопасных зон нет.");
                        for (Zone z : ZONES) ok(s, z.describe(), false);
                        return ZONES.size();
                    }
                }))
                .then(Commands.literal("info").executes(c -> {
                    CommandSourceStack s = c.getSource();
                    Vec3 p = s.getPosition();
                    String dim = dimOf(s);
                    int n = 0;
                    synchronized (ZONES) {
                        for (Zone z : ZONES) if (z.contains(dim, p.x(), p.z())) { ok(s, "Ты в зоне: " + z.describe(), false); n++; }
                    }
                    if (n == 0) return fail(s, "Здесь безопасной зоны нет.");
                    return n;
                }))
                .then(Commands.literal("pos1").executes(c -> setPos(c, true)))
                .then(Commands.literal("pos2").executes(c -> setPos(c, false)))
                .then(Commands.literal("create")
                        .then(Commands.argument("name", StringArgumentType.word()).executes(c -> {
                            CommandSourceStack s = c.getSource();
                            int[] a = POS1.get(s.getTextName()), b = POS2.get(s.getTextName());
                            if (a == null || b == null) return fail(s, "Сначала встань в углы и выполни /safezone pos1 и /safezone pos2.");
                            int r = addZone(s, StringArgumentType.getString(c, "name"), dimOf(s), a[0], a[1], b[0], b[1]);
                            if (r > 0) { POS1.remove(s.getTextName()); POS2.remove(s.getTextName()); }
                            return r;
                        })))
                .then(Commands.literal("add")
                        .then(Commands.argument("name", StringArgumentType.word())
                                .then(Commands.argument("x1", IntegerArgumentType.integer())
                                        .then(Commands.argument("z1", IntegerArgumentType.integer())
                                                .then(Commands.argument("x2", IntegerArgumentType.integer())
                                                        .then(Commands.argument("z2", IntegerArgumentType.integer()).executes(c ->
                                                                addZone(c.getSource(), StringArgumentType.getString(c, "name"), dimOf(c.getSource()),
                                                                        IntegerArgumentType.getInteger(c, "x1"), IntegerArgumentType.getInteger(c, "z1"),
                                                                        IntegerArgumentType.getInteger(c, "x2"), IntegerArgumentType.getInteger(c, "z2")))))))))
                .then(Commands.literal("remove")
                        .then(Commands.argument("name", StringArgumentType.word()).executes(c -> {
                            CommandSourceStack s = c.getSource();
                            String name = StringArgumentType.getString(c, "name");
                            synchronized (ZONES) {
                                if (!ZONES.removeIf(z -> z.name.equals(name))) return fail(s, "Зоны «" + name + "» нет. Список: /safezone list");
                                save();
                            }
                            ok(s, "Безопасная зона «" + name + "» удалена.", true);
                            return 1;
                        })))
                .then(Commands.literal("reload").executes(c -> {
                    load();
                    ok(c.getSource(), "Зоны перечитаны из файла: " + ZONES.size(), false);
                    return ZONES.size();
                })));
    }
}
