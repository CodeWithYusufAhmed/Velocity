package com.mdyusufahmed.velocity.ui.tables

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.SubcomposeAsyncImage
import com.mdyusufahmed.velocity.BuildConfig
import com.mdyusufahmed.velocity.data.MemberDto
import com.mdyusufahmed.velocity.ui.theme.Amber
import com.mdyusufahmed.velocity.ui.theme.NeonBlue

@Composable
fun Avatar(userId: Long, name: String, size: Int, hasAvatar: Boolean = true) {
    // Circular profile picture; falls back to initials while loading / when absent.
    SubcomposeAsyncImage(
        model = if (hasAvatar) "${BuildConfig.SERVER_BASE_URL}/users/$userId/avatar" else null,
        contentDescription = name,
        modifier = Modifier.size(size.dp).clip(CircleShape),
        error = { InitialsCircle(name, size) },
        loading = { InitialsCircle(name, size) },
    )
}

@Composable
private fun InitialsCircle(name: String, size: Int) {
    Box(
        Modifier.size(size.dp).clip(CircleShape).background(NeonBlue.copy(alpha = 0.25f)),
        contentAlignment = Alignment.Center,
    ) {
        Text(name.split(" ").mapNotNull { it.firstOrNull()?.uppercase() }
            .take(2).joinToString(""),
            style = MaterialTheme.typography.titleMedium, color = NeonBlue)
    }
}

@OptIn(ExperimentalFoundationApi::class, ExperimentalMaterial3Api::class)
@Composable
fun TableRoomScreen(tableId: Long, tableName: String, onExit: () -> Unit,
                    vm: TableRoomViewModel = hiltViewModel()) {
    val s by vm.state.collectAsState()
    var chatInput by remember { mutableStateOf("") }
    var menuFor by remember { mutableStateOf<MemberDto?>(null) }

    val permissions = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()) { }
    LaunchedEffect(tableId) {
        val wanted = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (android.os.Build.VERSION.SDK_INT >= 33)
            wanted += Manifest.permission.POST_NOTIFICATIONS  // the "in a Table" notification
        permissions.launch(wanted.toTypedArray())
        vm.join(tableId)
    }
    LaunchedEffect(s.closed) { if (s.closed) { vm.leave(); onExit() } }

    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        // Header
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text(tableName, style = MaterialTheme.typography.titleLarge,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text("${s.members.size} in the room", style = MaterialTheme.typography.labelSmall)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(0.dp)) {
                TextButton(onClick = { vm.openGifts(true) }) { Text("🎁") }
                if (s.myRole in listOf("owner", "admin")) {
                    TextButton(onClick = vm::openBanned) { Text("⛔") }
                }
                if (s.myRole == "owner") {
                    TextButton(onClick = vm::closeTable) { Text("Close") }
                }
                TextButton(onClick = { vm.leave(); onExit() }) { Text("Leave") }
            }
        }

        // VIP welcome (VIP2-4 banner; VIP5 full-screen splash below)
        s.welcome?.let { w ->
            if (w.vipTier in 2..4) {
                LaunchedEffect(w) { kotlinx.coroutines.delay(3000); vm.dismissWelcome() }
                Surface(shape = MaterialTheme.shapes.medium,
                    border = androidx.compose.foundation.BorderStroke(1.dp, Amber)) {
                    Text("👑 VIP${w.vipTier} ${w.name} joined the table!",
                        Modifier.fillMaxWidth().padding(8.dp), color = Amber)
                }
            }
        }

        // Chairs grid — avatar in the circle, name only underneath (Yusuf's rule)
        LazyVerticalGrid(columns = GridCells.Fixed(4),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            modifier = Modifier.heightIn(max = 260.dp)) {
            items(s.chairCount) { pos ->
                val occupantId = s.chairs[pos]
                val occupant = s.members.find { it.id == occupantId }
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(
                        Modifier.size(64.dp).clip(CircleShape)
                            .border(2.dp,
                                when {
                                    occupantId != null && occupantId in s.speaking ->
                                        androidx.compose.ui.graphics.Color(0xFF3FB950)
                                    occupantId != null -> MaterialTheme.colorScheme.outline
                                    else -> MaterialTheme.colorScheme.outlineVariant
                                }, CircleShape)
                            .combinedClickable(
                                // Single tap: empty chair = sit; my chair = stand;
                                // someone else = open their options (Yusuf's rule #8).
                                onClick = {
                                    when {
                                        occupant == null -> vm.tapChair(pos)
                                        s.seated == pos -> vm.tapChair(pos)
                                        else -> menuFor = occupant
                                    }
                                },
                                onLongClick = { occupant?.let { menuFor = it } },
                            ),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (occupant != null) Avatar(occupant.id, occupant.displayName, 60, occupant.hasAvatar)
                        else Text("＋", color = MaterialTheme.colorScheme.outline)
                        if (occupant?.muted == true) {
                            Text("🔇", modifier = Modifier.align(Alignment.TopEnd)
                                .background(androidx.compose.ui.graphics.Color(0xAAF85149), CircleShape)
                                .padding(2.dp),
                                style = MaterialTheme.typography.labelSmall)
                        }
                    }
                    Text(occupant?.displayName ?: "", maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.labelSmall)
                }
            }
        }

        // Listener list: owner first, then admins, then users (server pre-orders)
        Text("In the room", style = MaterialTheme.typography.labelMedium)
        LazyColumn(Modifier.weight(0.6f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            items(s.members) { m ->
                Row(Modifier.fillMaxWidth().clickable { menuFor = m }.padding(vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Avatar(m.id, m.displayName, 28, m.hasAvatar)
                    Text(m.displayName, style = MaterialTheme.typography.bodySmall)
                    if (m.vipTier > 0) Text("VIP${m.vipTier}", color = Amber,
                        style = MaterialTheme.typography.labelSmall)
                    if (m.role != "user") Text(m.role.uppercase(), color = NeonBlue,
                        style = MaterialTheme.typography.labelSmall)
                }
            }
        }

        // Chat
        LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp),
            reverseLayout = true) {
            items(s.chat.reversed()) { c ->
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (c.vipTier > 0) Text("VIP${c.vipTier}", color = Amber,
                        style = MaterialTheme.typography.labelSmall)
                    Text("${c.name}:", color = NeonBlue, style = MaterialTheme.typography.bodySmall)
                    Text(c.text, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(chatInput, { chatInput = it },
                placeholder = { Text("Message the table…") },
                singleLine = true, modifier = Modifier.weight(1f))
            IconButton(onClick = { vm.sendChat(chatInput); chatInput = "" }) { Text("➤") }
            FilledIconButton(
                onClick = vm::toggleMic, enabled = s.seated != null,
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = if (s.micOn) NeonBlue else MaterialTheme.colorScheme.surface),
            ) { Text(if (s.micOn) "🎙️" else "🔇") }
        }
    }

    // VIP5 full-screen splash — max 3s, tap to skip
    s.welcome?.let { w ->
        if (w.vipTier >= 5) {
            LaunchedEffect(w) { kotlinx.coroutines.delay(3000); vm.dismissWelcome() }
            Dialog(onDismissRequest = vm::dismissWelcome) {
                Surface(shape = MaterialTheme.shapes.extraLarge,
                    modifier = Modifier.fillMaxWidth().clickable { vm.dismissWelcome() }) {
                    Column(Modifier.padding(40.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("👑", style = MaterialTheme.typography.displayLarge)
                        Text("VIP5 ${w.name}", style = MaterialTheme.typography.headlineMedium,
                            color = Amber, textAlign = TextAlign.Center)
                        Text("has entered the table!", textAlign = TextAlign.Center)
                    }
                }
            }
        }
    }

    // Banned users sheet (owner/admin; unban is owner-only, server-enforced)
    val banned by vm.bannedList.collectAsState()
    banned?.let { list ->
        ModalBottomSheet(onDismissRequest = vm::closeBanned) {
            Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Blocked from this Table", style = MaterialTheme.typography.titleLarge)
                if (list.isEmpty()) Text("Nobody is blocked. 🎉")
                list.forEach { b ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(b.displayName)
                        if (s.myRole == "owner") {
                            Button(onClick = { vm.unbanFromTable(b.userId) }) { Text("Unban") }
                        }
                    }
                }
                Spacer(Modifier.height(16.dp))
            }
        }
    }

    // Gift teaser
    if (s.giftSheet) {
        ModalBottomSheet(onDismissRequest = { vm.openGifts(false) }) {
            Column(Modifier.padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("🎁 Gifts — coming soon", style = MaterialTheme.typography.titleLarge)
                Text("Fun, free, coin-based gifts are on the roadmap. Never paid — that's a promise.",
                    textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(24.dp))
            }
        }
    }

    // User card / moderation menu
    menuFor?.let { m ->
        val amOwner = s.myRole == "owner"
        val amAdmin = s.myRole == "admin"
        ModalBottomSheet(onDismissRequest = { menuFor = null }) {
            Column(Modifier.padding(horizontal = 24.dp, vertical = 8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Avatar(m.id, m.displayName, 40, m.hasAvatar)
                    Text(m.displayName + if (m.vipTier > 0) "  VIP${m.vipTier}" else "",
                        style = MaterialTheme.typography.titleMedium)
                }
                @Composable fun item(label: String, action: String) {
                    TextButton(onClick = { vm.moderate(action, m); menuFor = null },
                        modifier = Modifier.fillMaxWidth()) { Text(label) }
                }
                item("🚩 Report", "report")
                item("🔇 Block user (personal)", "block_personal")
                if ((amOwner || amAdmin) && m.role == "user") {
                    item("🔈 Mute", "mute")
                    item("👢 Kick", "kick")
                    item("💬 Ban from chat", "chat_ban")
                }
                if (amOwner && m.role != "owner") {
                    if (m.role == "admin") { item("🔈 Mute", "mute"); item("👢 Kick", "kick") }
                    item("⛔ Block from table", "block_table")
                    if (m.role == "user") item("⭐ Make admin", "make_admin")
                }
                Spacer(Modifier.height(16.dp))
            }
        }
    }

    s.notice?.let {
        LaunchedEffect(it) { kotlinx.coroutines.delay(2500); vm.dismissNotice() }
        Snackbar(Modifier.padding(8.dp)) { Text(it) }
    }
}
