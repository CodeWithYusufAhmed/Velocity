package com.mdyusufahmed.velocity.ui.game

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.hilt.navigation.compose.hiltViewModel
import com.mdyusufahmed.velocity.ui.theme.Amber
import com.mdyusufahmed.velocity.ui.theme.NeonBlue
import kotlin.math.cos
import kotlin.math.sin

/** Yusuf's arrangement: server slot position → clock angle (degrees, 0 = 12 o'clock).
 *  x45@12, x5@1:30, x15@3, x5@4:30, x25@6, x5@7:30, x10@9, x5@10:30. */
private val CLOCK_ANGLE = mapOf(
    7 to 0f,    // Bugatti x45
    0 to 45f,   // Toyota x5
    5 to 90f,   // Pagani x15
    2 to 135f,  // Honda x5
    6 to 180f,  // Mercedes-Maybach x25
    1 to 225f,  // Ford x5
    4 to 270f,  // Lamborghini x10
    3 to 315f,  // Nissan x5
)

private val CAR_EMOJI = mapOf(  // placeholder art: original vector cars are a follow-up
    0 to "🚗", 1 to "🚙", 2 to "🚕", 3 to "🚓", 4 to "🏎️", 5 to "🏎️", 6 to "🚘", 7 to "🏎️")

@Composable
fun GameScreen(vm: GameViewModel = hiltViewModel()) {
    val s by vm.state.collectAsState()

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {

        // Header: round number + balance
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            Text("Round #${"%,d".format(s.roundId)}", style = MaterialTheme.typography.labelLarge)
            Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surface) {
                Text("🪙 ${"%,d".format(s.balance)}", color = Amber,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
            }
        }
        if (!s.connected) Text("○ Reconnecting…", color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelSmall)

        // Result strip (last 50)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            items(s.recent) { r ->
                Surface(shape = RoundedCornerShape(8.dp), color = MaterialTheme.colorScheme.surface) {
                    Column(Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(CAR_EMOJI[r.winningPosition] ?: "🚗")
                        Text("x${r.multiplier}", color = Amber,
                            style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }

        // The wheel
        Wheel(s, onSlotTap = vm::tapSlot, modifier = Modifier.weight(1f))

        // Status row
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Today's winning: +${"%,d".format(s.todayWon)}",
                color = WinGreen, style = MaterialTheme.typography.labelMedium)
            Text("You didn't spend: $${"%.2f".format(s.moneyNotSpent)}",
                color = Amber, style = MaterialTheme.typography.labelMedium)
        }

        // Bonus pill
        if (s.bonusReady) {
            Surface(shape = CircleShape, border = androidx.compose.foundation.BorderStroke(1.dp, Amber)) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically) {
                    Text("🎁 Daily bonus: 50,000", style = MaterialTheme.typography.labelLarge)
                    Button(onClick = vm::claimBonus, contentPadding = PaddingValues(horizontal = 14.dp)) {
                        Text("Claim")
                    }
                }
            }
        }

        // Chip row OR limit-reached panel
        if (s.limitReached) {
            Surface(shape = RoundedCornerShape(12.dp), color = MaterialTheme.colorScheme.surface) {
                Text("You reached your daily round limit. Enjoy watching — betting opens " +
                     "again after midnight (Dhaka time).",
                    Modifier.padding(12.dp), textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodySmall)
            }
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                CHIPS.forEach { chip ->
                    val on = s.selectedChip == chip
                    Box(
                        Modifier.size(44.dp).clip(CircleShape)
                            .background(MaterialTheme.colorScheme.surface)
                            .border(2.dp, if (on) Amber else MaterialTheme.colorScheme.outline,
                                CircleShape)
                            .clickable { vm.selectChip(chip) },
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(if (chip >= 1000) "${chip / 1000}K" else "$chip",
                            color = if (on) Amber else MaterialTheme.colorScheme.onSurface,
                            style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }
    }

    s.result?.let { ResultOverlay(it, onDismiss = vm::dismissResult) }
    if (s.rescueOffered) RescueSheet(rescuesLeft = s.rescuesLeft,
        onClaim = vm::claimRescue, onDismiss = { vm.state.value = s.copy(rescueOffered = false) })
    s.error?.let {
        LaunchedEffect(it) { kotlinx.coroutines.delay(2500); vm.dismissError() }
        Snackbar(Modifier.padding(8.dp)) { Text(it) }
    }
}

@Composable
private fun Wheel(s: GameUiState, onSlotTap: (Int) -> Unit, modifier: Modifier = Modifier) {
    // Spin presentation: a highlight sweeps around the ring and decelerates onto
    // the server's winning slot. Pure presentation — the result is already fixed.
    val sweep = remember { Animatable(0f) }
    LaunchedEffect(s.result?.winningPosition, s.phase) {
        val winner = s.result?.winningPosition
        if (s.phase == "SPINNING") {
            sweep.snapTo(0f)
            sweep.animateTo(360f * 4, tween(2600, easing = CubicBezierEasing(0.1f, 0.7f, 0.2f, 1f)))
        } else if (winner != null) {
            sweep.snapTo(CLOCK_ANGLE[winner] ?: 0f)
        }
    }
    val highlightAngle = ((sweep.value % 360f) + 360f) % 360f

    Layout(
        modifier = modifier.fillMaxWidth(),
        content = {
            // Hub (first child)
            Column(
                Modifier.size(110.dp).clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surface)
                    .border(3.dp, NeonBlue, CircleShape),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(if (s.phase == "BETTING") "${s.secondsLeft}" else "•",
                    style = MaterialTheme.typography.displaySmall, color = NeonBlue)
                Text(when (s.phase) {
                    "BETTING" -> "PLACE YOUR BETS"
                    "SPINNING" -> "SPINNING…"
                    else -> "RESULTS"
                }, style = MaterialTheme.typography.labelSmall)
            }
            // 8 slots
            (0..7).forEach { pos ->
                val slot = s.odds.getOrNull(pos)
                val angle = CLOCK_ANGLE[pos] ?: 0f
                val active = s.phase == "SPINNING" &&
                    angleDistance(angle, highlightAngle) < 22.5f
                val betOn = (s.myBets[pos] ?: 0L) > 0L
                Box {
                    Column(
                        Modifier.size(width = 84.dp, height = 58.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(MaterialTheme.colorScheme.surface)
                            .border(1.dp,
                                when {
                                    active -> Amber
                                    betOn -> NeonBlue
                                    else -> MaterialTheme.colorScheme.outline
                                }, RoundedCornerShape(12.dp))
                            .clickable { onSlotTap(pos) },
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Text(CAR_EMOJI[pos] ?: "🚗")
                        Text(slot?.name?.take(8) ?: "…", style = MaterialTheme.typography.labelSmall)
                        Text("x${slot?.multiplier ?: 0}", color = Amber,
                            style = MaterialTheme.typography.labelSmall)
                    }
                    if (betOn) {
                        Surface(shape = CircleShape, color = NeonBlue,
                            modifier = Modifier.align(Alignment.TopEnd)) {
                            Text("%,d".format(s.myBets[pos]),
                                Modifier.padding(horizontal = 5.dp, vertical = 1.dp),
                                color = androidx.compose.ui.graphics.Color.White,
                                style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        },
    ) { measurables, constraints ->
        val size = minOf(constraints.maxWidth, constraints.maxHeight)
        val loose = Constraints()
        val hub = measurables.first().measure(loose)
        val slots = measurables.drop(1).map { it.measure(loose) }
        val radius = size / 2f - slots.first().height / 2f - 8
        layout(size, size) {
            hub.placeRelative((size - hub.width) / 2, (size - hub.height) / 2)
            slots.forEachIndexed { pos, p ->
                val a = Math.toRadians(((CLOCK_ANGLE[pos] ?: 0f) - 90f).toDouble())
                val cx = size / 2f + radius * cos(a).toFloat()
                val cy = size / 2f + radius * sin(a).toFloat()
                p.placeRelative((cx - p.width / 2).toInt(), (cy - p.height / 2).toInt())
            }
        }
    }
}

private fun angleDistance(a: Float, b: Float): Float {
    val d = Math.abs(a - b) % 360f
    return if (d > 180f) 360f - d else d
}

private val WinGreen = androidx.compose.ui.graphics.Color(0xFF3FB950)

@Composable
private fun ResultOverlay(r: SpinResult, onDismiss: () -> Unit) {
    LaunchedEffect(r) { kotlinx.coroutines.delay(3000); onDismiss() }
    Dialog(onDismissRequest = onDismiss) {
        Surface(shape = RoundedCornerShape(20.dp)) {
            Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(CAR_EMOJI[r.winningPosition] ?: "🚗",
                    style = MaterialTheme.typography.displayMedium)
                Text("${r.winningName}  x${r.multiplier}",
                    style = MaterialTheme.typography.titleLarge, color = Amber)
                if (r.myPayout > 0)
                    Text("You won ${"%,d".format(r.myPayout)}!",
                        color = WinGreen, style = MaterialTheme.typography.titleMedium)
                if (r.top3.isNotEmpty()) {
                    HorizontalDivider()
                    Text("Top winners", style = MaterialTheme.typography.labelMedium)
                    r.top3.forEachIndexed { i, t ->
                        Text("${listOf("🥇", "🥈", "🥉")[i]} ${t.displayName} — ${"%,d".format(t.won)}",
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RescueSheet(rescuesLeft: Int, onClaim: () -> Unit, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Out of coins?", style = MaterialTheme.typography.titleLarge)
            Text("Grab a free 20,000-coin rescue. $rescuesLeft left today. " +
                 "Remember: coins are free here — always.", textAlign = TextAlign.Center)
            Button(onClick = onClaim, Modifier.fillMaxWidth()) { Text("Rescue me (+20,000)") }
            Spacer(Modifier.height(16.dp))
        }
    }
}
