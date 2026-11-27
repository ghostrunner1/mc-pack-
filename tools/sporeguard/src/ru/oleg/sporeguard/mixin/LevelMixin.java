package ru.oleg.sporeguard.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import ru.oleg.sporeguard.SporeGuard;

@Mixin(Level.class)
public abstract class LevelMixin {
    @Inject(method = "setBlock(Lnet/minecraft/core/BlockPos;Lnet/minecraft/world/level/block/state/BlockState;II)Z", at = @At("HEAD"), cancellable = true)
    private void sporeguard$setBlock(BlockPos pos, BlockState state, int flags, int recursion, CallbackInfoReturnable<Boolean> cir) {
        if (!SporeGuard.active()) return;
        Level level = (Level) (Object) this;
        if (level.isClientSide()) return;
        if (!level.getBlockState(pos).isAir()) cir.setReturnValue(false);
    }

    @Inject(method = "destroyBlock(Lnet/minecraft/core/BlockPos;ZLnet/minecraft/world/entity/Entity;I)Z", at = @At("HEAD"), cancellable = true)
    private void sporeguard$destroyBlock(BlockPos pos, boolean drop, Entity entity, int recursion, CallbackInfoReturnable<Boolean> cir) {
        if (SporeGuard.isSpore(entity) || (SporeGuard.active() && !((Level) (Object) this).isClientSide())) cir.setReturnValue(false);
    }
}
